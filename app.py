import os
import glob
import hashlib
import json
import secrets as pysecrets
import threading
import time
import uuid
import urllib.request
from datetime import timedelta

import numpy as np
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, request, Response, redirect, session
from google.cloud import storage
from itsdangerous import BadSignature, SignatureExpired

import auth
from precompute import process_h5, recommend_peak_count
from fit import perform_fits

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'app-hyperspec')
CRUCIBLE_EXPLORE_URL = os.environ.get('CRUCIBLE_EXPLORE_URL', '').rstrip('/')
HYPERSPEC_SSO_SECRET = os.environ.get('HYPERSPEC_SSO_SECRET', '')

app = Flask(__name__, static_folder='frontend/dist', static_url_path='')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Local development: use the service-account key kept next to this file for
# GCS access. The key is dockerignored, so this never triggers on Cloud Run,
# which authenticates through its runtime service account instead.
if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
    _local_keys = glob.glob(os.path.join(BASE_DIR, 'mf-crucible*.json'))
    if _local_keys:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = _local_keys[0]

# ── Sessions ──────────────────────────────────────────────────────────────────
# The signed session cookie is the only carrier of identity. All Hyperspec
# containers must share SECRET_KEY (Secret Manager) so a session minted by one
# instance/revision is valid on every other one.
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    print("WARNING: SECRET_KEY not set — using a random per-boot key; "
          "sessions will not survive restarts or span multiple containers.")
    _secret = pysecrets.token_hex(32)
app.secret_key = _secret
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_HTTPONLY=True,
    # K_SERVICE is set by Cloud Run; local http dev keeps non-Secure cookies
    SESSION_COOKIE_SECURE=bool(os.environ.get('K_SERVICE')),
)

_sso_serializer = auth.make_serializer(HYPERSPEC_SSO_SECRET) if HYPERSPEC_SSO_SECRET else None

default_data_path = os.path.join(BASE_DIR, 'precomputed_data.json')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ── In-memory state ───────────────────────────────────────────────────────────
# Working copies of datasets, keyed by (principal, dataset_id). Every request
# resolves its principal from the session, so one user's edits (pixel peak
# overrides, fits, ...) can never be observed through another principal's key.
datasets = {}
processing_status = {}   # (principal, dataset_id) -> status dict

DEFAULT_NAME = 'default (MAPPING.h5)'
default_dataset = None
if os.path.exists(default_data_path):
    try:
        with open(default_data_path, 'r') as f:
            default_dataset = json.load(f)
    except json.JSONDecodeError:
        print("Warning: precomputed_data.json is corrupted or is a Git LFS pointer file. "
              "Default dataset will not be loaded.")


# ── GCS helpers (best-effort: local dev without credentials degrades) ────────
_storage_client = None


def _bucket():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client.bucket(BUCKET_NAME)


def _gcs_read_text(path):
    try:
        return _bucket().blob(path).download_as_bytes().decode('utf-8')
    except Exception:
        return None


def _gcs_write_text(path, text):
    try:
        _bucket().blob(path).upload_from_string(text, content_type='application/json')
        return True
    except Exception as e:
        print(f"GCS write failed for {path}: {e}")
        return False


def _gcs_read_json(path):
    text = _gcs_read_text(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _gcs_write_json(path, obj):
    return _gcs_write_text(path, json.dumps(obj, separators=(',', ':')))


def _gcs_delete(path):
    try:
        _bucket().blob(path).delete()
    except Exception:
        pass


# ── Per-principal storage layout ──────────────────────────────────────────────
# ORCiD users (durable, shared by every Hyperspec container):
#   gs://<bucket>/users/<orcid>/registry.json           {id: {name, sha256}}
#   gs://<bucket>/users/<orcid>/datasets/<id>.json      working copies
# Anonymous users: registry lives in the session cookie; working copies in
# memory + this container's disk (ephemeral by design).
# Every upload is processed fresh — there is deliberately no shared cache of
# precompute results, so pipeline improvements always apply immediately.

def _registry_path(orcid):
    return f'users/{orcid}/registry.json'


def _workcopy_path(orcid, dsid):
    return f'users/{orcid}/datasets/{dsid}.json'


def _pid_token(principal):
    """Opaque, deterministic per-principal prefix for temp upload objects."""
    return hashlib.sha1(principal.encode()).hexdigest()[:16]


def _anon_work_path(principal, dsid):
    d = os.path.join(UPLOAD_FOLDER, 'anon_work', _pid_token(principal))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{dsid}.json')


# ── Registry: which dataset ids a principal may touch ─────────────────────────

def registry_get(principal):
    if auth.is_orcid(principal):
        return _gcs_read_json(_registry_path(auth.orcid_of(principal))) or {}
    return session.get('registry') or {}


def registry_put(principal, dsid, name, sha):
    entry = {'name': name, 'sha256': sha}
    if auth.is_orcid(principal):
        orcid = auth.orcid_of(principal)
        reg = _gcs_read_json(_registry_path(orcid)) or {}
        reg[dsid] = entry
        _gcs_write_json(_registry_path(orcid), reg)
    else:
        reg = session.get('registry') or {}
        reg[dsid] = entry
        session['registry'] = reg
        session.modified = True


def registry_remove(principal, dsid):
    if auth.is_orcid(principal):
        orcid = auth.orcid_of(principal)
        reg = _gcs_read_json(_registry_path(orcid)) or {}
        if dsid in reg:
            del reg[dsid]
            _gcs_write_json(_registry_path(orcid), reg)
    else:
        reg = session.get('registry') or {}
        if dsid in reg:
            del reg[dsid]
            session['registry'] = reg
            session.modified = True


# ── Working-copy access ───────────────────────────────────────────────────────

def load_working(principal, dsid):
    """Return the dataset visible to `principal` under `dsid`, or None.

    Resolution order: in-memory working copy → persisted working copy
    (GCS for orcid, local disk for anon). The shared demo `default` is
    readable by everyone; reads get the shared object, writes go through
    ensure_writable() which makes a private copy first.
    """
    key = (principal, dsid)
    if key in datasets:
        return datasets[key]

    if dsid == 'default':
        if auth.is_orcid(principal):
            data = _gcs_read_json(_workcopy_path(auth.orcid_of(principal), 'default'))
            if data is not None:
                datasets[key] = data
                return data
        return default_dataset

    entry = registry_get(principal).get(dsid)
    if not entry:
        return None

    if auth.is_orcid(principal):
        data = _gcs_read_json(_workcopy_path(auth.orcid_of(principal), dsid))
        if data is not None:
            datasets[key] = data
            return data
    else:
        local = _anon_work_path(principal, dsid)
        if os.path.exists(local):
            with open(local, 'r') as f:
                data = json.load(f)
            datasets[key] = data
            return data

    return None


def ensure_writable(principal, dsid):
    """Like load_working, but guarantees a private mutable copy (copy-on-write
    for the shared default demo)."""
    data = load_working(principal, dsid)
    if data is None:
        return None
    key = (principal, dsid)
    if key not in datasets:
        # Shared/default object — never mutate it; clone into the namespace
        datasets[key] = json.loads(json.dumps(data))
    return datasets[key]


def flush_working(principal, dsid):
    """Persist the principal's working copy (GCS for orcid, disk for anon)."""
    data = datasets.get((principal, dsid))
    if data is None:
        return
    text = json.dumps(data, separators=(',', ':'))
    if auth.is_orcid(principal):
        _gcs_write_text(_workcopy_path(auth.orcid_of(principal), dsid), text)
    else:
        with open(_anon_work_path(principal, dsid), 'w') as f:
            f.write(text)


# ── Ingestion pipeline ────────────────────────────────────────────────────────

def _sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def process_file_background(principal, filepath, dsid):
    key = (principal, dsid)
    processing_status[key] = {'status': 'processing', 'current': 0, 'total': 1,
                              'message': 'Initializing...'}

    def update_progress(current, total, message):
        processing_status[key] = {'status': 'processing', 'current': current,
                                  'total': total, 'message': message}

    try:
        data = process_h5(filepath, progress_callback=update_progress)
        datasets[key] = data
        # Persist immediately — the working copy is the only durable record
        # of this dataset (GCS for orcid, local disk for anon).
        flush_working(principal, dsid)
        processing_status[key] = {'status': 'done', 'dataset_id': dsid}
    except Exception as e:
        registry_remove_safe = auth.is_orcid(principal)
        if registry_remove_safe:
            # anon registries live in the cookie and can't be edited here;
            # their stale entry just 404s later.
            registry_remove(principal, dsid)
        processing_status[key] = {'status': 'error', 'error': str(e)}
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


def ingest_local_file(principal, filepath, filename):
    """Hash, register, and process a file for a principal.

    Returns (dataset_id, duplicate). Must run inside a request context (it
    may write the anon registry into the session cookie).
    """
    sha = _sha256_file(filepath)
    dsid = sha[:8]
    key = (principal, dsid)

    reg = registry_get(principal)
    duplicate = dsid in reg
    if not duplicate:
        registry_put(principal, dsid, filename, sha)

    if duplicate and (key in datasets or load_working(principal, dsid) is not None):
        os.remove(filepath)
        return dsid, True

    threading.Thread(target=process_file_background,
                     args=(principal, filepath, dsid),
                     daemon=True).start()
    return dsid, duplicate


# ── Crucible SSO / import ─────────────────────────────────────────────────────

@app.route('/import')
def import_from_crucible():
    """Entry point for Crucible-signed tokens.

    Identity (ORCiD) and the object to ingest come exclusively from the
    verified token — never from other request parameters.
    """
    if _sso_serializer is None:
        return "Crucible integration is not configured on this Hyperspec instance.", 503
    token = request.args.get('token', '')
    try:
        payload = auth.verify_import_token(_sso_serializer, token)
    except SignatureExpired:
        return ("This Crucible link has expired — go back to Crucible and click "
                "\"Open in Hyperspec\" again."), 403
    except BadSignature:
        return "Invalid Crucible token.", 403

    auth.login_orcid(payload['orcid'], payload.get('name'))
    principal = f"orcid:{payload['orcid']}"

    object_name = payload.get('object')
    signed_url = payload.get('signed_url')
    if not object_name and not signed_url:
        return redirect('/')  # login-only bounce

    filename = secure_filename(payload.get('filename') or 'import.h5')
    local = os.path.join(UPLOAD_FOLDER, f'import_{uuid.uuid4().hex}_{filename}')
    try:
        if object_name:
            # Crucible only ever writes under incoming/ (write-only IAM grant)
            if not object_name.startswith('incoming/'):
                return "Invalid import object.", 400
            _bucket().blob(object_name).download_to_filename(local)
        else:
            if not signed_url.startswith('https://'):
                return "Invalid import URL.", 400
            with urllib.request.urlopen(signed_url) as resp, open(local, 'wb') as out:
                while chunk := resp.read(1024 * 1024):
                    out.write(chunk)
    except Exception as e:
        if os.path.exists(local):
            os.remove(local)
        return f"Could not fetch the file from Crucible: {e}", 502

    dsid, _ = ingest_local_file(principal, local, filename)
    if object_name:
        _gcs_delete(object_name)
    return redirect(f'/?dataset={dsid}')


@app.route('/config')
def client_config():
    principal = auth.get_principal()
    identity = {'type': 'orcid' if auth.is_orcid(principal) else 'anon'}
    if auth.is_orcid(principal):
        identity['orcid'] = auth.orcid_of(principal)
        identity['name'] = session.get('display_name') or identity['orcid']
    return jsonify({
        'identity': identity,
        'sign_in_url': f'{CRUCIBLE_EXPLORE_URL}/hyperspec/sso' if CRUCIBLE_EXPLORE_URL else None,
    })


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


# ── Upload flow (browser → signed PUT → process) ─────────────────────────────

def _ingest_response(principal, local, filename):
    """Shared tail of every upload route: ingest and describe the outcome."""
    dsid, duplicate = ingest_local_file(principal, local, filename)
    if duplicate:
        name = registry_get(principal).get(dsid, {}).get('name', dsid)
        return jsonify({
            "message": f"Dataset already exists as '{name}'.",
            "dataset_id": dsid,
            "filename": filename,
            "duplicate": True
        })
    return jsonify({
        "message": "File processing started",
        "dataset_id": dsid,
        "filename": filename,
        "duplicate": False
    })


@app.route('/upload_direct', methods=['POST'])
def upload_direct():
    """Direct multipart upload, used by the local dev frontend.

    The production flow goes browser → GCS signed PUT → /process_gcs_file
    because Cloud Run caps request bodies at 32 MiB; locally that hop only
    adds cloud-credential and bucket-CORS failure modes, so the dev build
    posts the file straight here instead.
    """
    principal = auth.get_principal()
    f = request.files.get('file')
    if f is None:
        return jsonify({"error": "No file provided"}), 400
    filename = secure_filename(f.filename or 'upload.h5')
    local = os.path.join(UPLOAD_FOLDER, f'upload_{uuid.uuid4().hex}_{filename}')
    try:
        f.save(local)
        return _ingest_response(principal, local, filename)
    except Exception as e:
        if os.path.exists(local):
            os.remove(local)
        return jsonify({"error": str(e)}), 500

def generate_signed_put_url(blob):
    """
    Sign a V4 PUT URL for the blob.

    In production (Cloud Run) the default credentials are token-only — there is
    no private key on the box — so signing MUST go through the IAM SignBlob API.
    This requires the runtime service account to have
    roles/iam.serviceAccountTokenCreator on itself.

    In local development, credentials from a service-account JSON key
    (GOOGLE_APPLICATION_CREDENTIALS) carry a private key and can sign directly.
    """
    import datetime
    import google.auth
    from google.auth import credentials as gauth_credentials
    from google.auth.transport import requests as gauth_requests

    kwargs = dict(
        version="v4",
        expiration=datetime.timedelta(minutes=15),
        method="PUT",
        content_type="application/octet-stream",
    )

    credentials, _ = google.auth.default()
    if isinstance(credentials, gauth_credentials.Signing):
        # Local development: key-based credentials sign directly
        return blob.generate_signed_url(**kwargs)

    # Production path: token-only credentials, sign via IAM SignBlob
    credentials.refresh(gauth_requests.Request())
    return blob.generate_signed_url(
        **kwargs,
        service_account_email=credentials.service_account_email,
        access_token=credentials.token,
    )


@app.route('/generate_upload_url', methods=['POST'])
def generate_upload_url():
    principal = auth.get_principal()
    data = request.json
    filename = secure_filename(data.get('filename', 'upload.h5'))
    # Prefix-locked per principal: /process_gcs_file only accepts objects here
    object_name = f"uploads-tmp/{_pid_token(principal)}/{uuid.uuid4()}_{filename}"

    try:
        blob = _bucket().blob(object_name)
        url = generate_signed_put_url(blob)
        return jsonify({"signed_url": url, "object_name": object_name, "filename": filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/process_gcs_file', methods=['POST'])
def process_gcs_file():
    principal = auth.get_principal()
    data = request.json
    object_name = data.get('object_name')
    filename = data.get('filename')

    if not object_name or not filename:
        return jsonify({"error": "Missing object_name or filename"}), 400
    # A principal may only process objects it was issued an upload URL for
    if not object_name.startswith(f"uploads-tmp/{_pid_token(principal)}/"):
        return jsonify({"error": "Object does not belong to this session"}), 403

    filename = secure_filename(filename)
    local = os.path.join(UPLOAD_FOLDER, f'upload_{uuid.uuid4().hex}_{filename}')
    try:
        _bucket().blob(object_name).download_to_filename(local)
        response = _ingest_response(principal, local, filename)
        _gcs_delete(object_name)
        return response
    except Exception as e:
        if os.path.exists(local):
            os.remove(local)
        return jsonify({"error": str(e)}), 500


# ── Dataset routes (all scoped to the session principal) ─────────────────────

@app.route('/status/<dataset_id>')
def get_status(dataset_id):
    principal = auth.get_principal()
    key = (principal, dataset_id)
    if key in processing_status:
        return jsonify(processing_status[key])
    if load_working(principal, dataset_id) is not None:
        return jsonify({'status': 'done', 'dataset_id': dataset_id})
    return jsonify({'status': 'not_found'}), 404


@app.route('/datasets')
def list_datasets():
    principal = auth.get_principal()
    res = []
    if default_dataset is not None:
        res.append({"id": "default", "name": DEFAULT_NAME})
    for dsid, entry in registry_get(principal).items():
        res.append({"id": dsid, "name": entry.get('name', dsid)})
    return jsonify({"datasets": res})


@app.route('/update_pixel/<dataset_id>/<pixel_key>', methods=['POST'])
def update_pixel(dataset_id, pixel_key):
    principal = auth.get_principal()
    data = request.json
    dataset = ensure_writable(principal, dataset_id)
    if dataset is not None and pixel_key in dataset['pixels']:
        pixel = dataset['pixels'][pixel_key]
        if 'num_peaks' in data:
            pixel['expected_num_peaks'] = int(data['num_peaks'])
            pixel['needs_refit'] = True
            pixel['changed'] = True
        return jsonify({"success": True})
    return jsonify({"error": "Dataset or pixel not found"}), 404


@app.route('/reset_all_fits/<dataset_id>', methods=['POST'])
def reset_all_fits(dataset_id):
    principal = auth.get_principal()
    dataset = ensure_writable(principal, dataset_id)
    if dataset is None:
        return jsonify({"error": "Dataset not found"}), 404

    rs = dataset['global_axes']['rs']
    for key, pixel in dataset['pixels'].items():
        if pixel.get('changed', False):
            pixel['fit_success'] = False
            pixel['needs_refit'] = True
            pixel['changed'] = False
            pixel.pop('expected_num_peaks', None)
            pixel['fit_curves'] = []
            pixel['total_fit_curve'] = []
            pixel['r_squared'] = 0.0

            n_peaks, p_indices = recommend_peak_count(rs, pixel['norm_spec'])
            pixel['num_peaks'] = n_peaks
            pixel['peak_indices'] = p_indices

    return jsonify({"success": True})


@app.route('/detect_flake/<dataset_id>', methods=['GET'])
def detect_flake(dataset_id):
    principal = auth.get_principal()
    dataset = load_working(principal, dataset_id)
    if dataset is None:
        return jsonify({"error": "Dataset not found"}), 404

    try:
        import cv2
    except ImportError:
        return jsonify({"error": "OpenCV not installed on server"}), 500

    map_type = request.args.get('map_type', 'integrated_intensity')

    width = dataset['global_axes']['width']
    height = dataset['global_axes']['height']

    # Reconstruct the 2D grid
    grid = np.zeros((height, width), dtype=np.float32)
    valid_pixels = 0
    for y in range(height):
        for x in range(width):
            h_idx = (width - 1) - x
            key = f"{h_idx}_{y}"
            if key in dataset['pixels']:
                val = dataset['pixels'][key].get(map_type)
                if val is None:
                    val = 0.0
                grid[y, x] = float(val)
                valid_pixels += 1

    if valid_pixels == 0:
        return jsonify({"error": "No valid data"}), 400

    min_val = np.min(grid)
    max_val = np.max(grid)
    if max_val > min_val:
        grid_norm = np.uint8(255 * (grid - min_val) / (max_val - min_val))
    else:
        grid_norm = np.zeros_like(grid, dtype=np.uint8)

    blurred = cv2.GaussianBlur(grid_norm, (0, 0), 1.0)

    # Otsu's thresholding
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morphological Cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
    cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_contour = None
    best_area = 0
    total_area = width * height

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < total_area * 0.02:
            continue

        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue

        solidity = area / hull_area

        if solidity > 0.5:
            if area > best_area:
                best_area = area
                best_contour = cnt

    if best_contour is None:
        return jsonify({"error": "Shape not found. Try switching to a different Map Type."}), 404

    # Simplify contour for frontend rendering
    epsilon = 0.01 * cv2.arcLength(best_contour, True)
    approx = cv2.approxPolyDP(best_contour, epsilon, True)

    points = []
    for pt in approx:
        x, y = pt[0]
        points.append({"x": int(x), "y": int(y)})

    # Calculate average spectrum for the flake
    flake_mask = np.zeros((height, width), dtype=np.uint8)
    cv2.drawContours(flake_mask, [best_contour], -1, 255, -1)

    specs = []
    for y in range(height):
        for x in range(width):
            if flake_mask[y, x] == 255:
                h_idx = (width - 1) - x
                key = f"{h_idx}_{y}"
                if key in dataset['pixels']:
                    spec = dataset['pixels'][key].get('norm_spec')
                    if spec is not None:
                        specs.append(spec)

    if len(specs) > 0:
        specs_arr = np.array(specs)
        mean_spec = np.mean(specs_arr, axis=0).tolist()
        std_spec = np.std(specs_arr, axis=0).tolist()
    else:
        mean_spec = []
        std_spec = []

    return jsonify({
        "points": points,
        "mean_spec": mean_spec,
        "std_spec": std_spec
    })


@app.route('/rename/<dataset_id>', methods=['POST'])
def rename_dataset(dataset_id):
    principal = auth.get_principal()
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"error": "No name provided"}), 400
    if dataset_id == 'default':
        return jsonify({"error": "Cannot rename default dataset"}), 403
    reg = registry_get(principal)
    if dataset_id not in reg:
        return jsonify({"error": "Dataset not found"}), 404
    registry_put(principal, dataset_id, data['name'], reg[dataset_id].get('sha256'))
    return jsonify({"success": True, "name": data['name']})


@app.route('/dataset/<dataset_id>', methods=['DELETE'])
def delete_dataset(dataset_id):
    principal = auth.get_principal()
    if dataset_id == 'default':
        return jsonify({"error": "Cannot delete default dataset"}), 403

    reg = registry_get(principal)
    if dataset_id not in reg:
        return jsonify({"error": "Dataset not found"}), 404

    registry_remove(principal, dataset_id)
    datasets.pop((principal, dataset_id), None)
    processing_status.pop((principal, dataset_id), None)
    if auth.is_orcid(principal):
        _gcs_delete(_workcopy_path(auth.orcid_of(principal), dataset_id))
    else:
        local = _anon_work_path(principal, dataset_id)
        if os.path.exists(local):
            os.remove(local)
    return jsonify({"success": True})


@app.route('/api/data/<dataset_id>')
def get_dataset(dataset_id):
    principal = auth.get_principal()
    # Wait for the dataset to finish background processing/loading
    for _ in range(600):  # up to 60 seconds
        data = load_working(principal, dataset_id)
        if data is not None:
            import gzip
            payload = json.dumps(data)
            compressed = gzip.compress(payload.encode('utf-8'), compresslevel=1)

            # Stream compressed chunks: Cloud Run caps non-chunked responses at 32 MiB,
            # and large datasets exceed that even when compressed.
            def generate():
                for i in range(0, len(compressed), 1024 * 1024):
                    yield compressed[i:i + 1024 * 1024]

            response = Response(generate(), mimetype='application/json')
            response.headers['Content-Encoding'] = 'gzip'
            return response
        status = processing_status.get((principal, dataset_id))
        if status is not None and status.get('status') == 'error':
            return jsonify({"error": status.get('error')}), 500
        if status is None:
            break  # not this principal's dataset — don't hold the connection
        time.sleep(0.1)
    return jsonify({"error": "Dataset not found or still loading"}), 404


@app.route('/fit_stream/<dataset_id>')
def fit_stream(dataset_id):
    # Resolve principal and working copy NOW — the generator below runs while
    # streaming, outside the request context, and must not touch the session.
    principal = auth.get_principal()
    dataset = ensure_writable(principal, dataset_id)
    fit_mode = request.args.get('mode', 'pseudo_voigt')

    def generate():
        # Using SSE to stream fit results
        if dataset is None:
            yield f"data: {json.dumps({'error': 'Dataset not found'})}\n\n"
            return
        try:
            for result in perform_fits(dataset_id, {dataset_id: dataset}, mode=fit_mode):
                yield f"data: {json.dumps(result)}\n\n"

            # Persist the principal's working copy exactly once at the end
            flush_working(principal, dataset_id)

            yield "data: {\"done\": true}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/')
def serve_index():
    return app.send_static_file('index.html')


@app.route('/<path:path>')
def serve_static(path):
    return app.send_static_file(path)


if __name__ == '__main__':
    print("Starting server...")
    app.run(host='0.0.0.0', debug=True, port=8080)
