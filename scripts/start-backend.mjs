// Bootstraps the Python backend for `npm run dev`.
//
// Creates ./venv if it doesn't exist, keeps it in sync with requirements.txt,
// and runs app.py with the venv's interpreter — never the system Python.
// Cross-platform (the venv layout differs between Windows and POSIX).
import { existsSync } from 'node:fs'
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const isWin = process.platform === 'win32'
const venvPython = path.join(root, 'venv', ...(isWin ? ['Scripts', 'python.exe'] : ['bin', 'python']))

function run(cmd, args) {
  const res = spawnSync(cmd, args, { cwd: root, stdio: 'inherit' })
  if (res.error || res.status !== 0) {
    console.error(`[hyperspec] ${cmd} ${args.join(' ')} failed`)
    process.exit(res.status ?? 1)
  }
}

if (!existsSync(venvPython)) {
  console.log('[hyperspec] Creating Python virtual environment in ./venv ...')
  const systemPython = !isWin && spawnSync('python3', ['--version']).status === 0 ? 'python3' : 'python'
  run(systemPython, ['-m', 'venv', 'venv'])
}

console.log('[hyperspec] Syncing dependencies from requirements.txt ...')
run(venvPython, ['-m', 'pip', 'install', '--quiet', '-r', 'requirements.txt'])

const child = spawn(venvPython, ['-u', 'app.py'], { cwd: root, stdio: 'inherit' })
child.on('exit', (code) => process.exit(code ?? 0))
