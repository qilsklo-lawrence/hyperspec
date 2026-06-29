import socket
import threading
import sys

def pipe(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            src.close()
        except:
            pass
        try:
            dst.close()
        except:
            pass

def main():
    local_port = 8080
    target_port = 8080
    
    # Listen on all interfaces (0.0.0.0)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('0.0.0.0', local_port))
    except Exception as e:
        print(f"Error binding to port {local_port}: {e}")
        sys.exit(1)
        
    server.listen(10)
    print(f"Port forwarder running. Listening on 0.0.0.0:{local_port} -> 127.0.0.1:{target_port}")
    
    try:
        while True:
            client_sock, addr = server.accept()
            # Connect to the local end of the SSH tunnel
            target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                target_sock.connect(('127.0.0.1', target_port))
                # Spawn threads to pipe data bidirectionally
                threading.Thread(target=pipe, args=(client_sock, target_sock), daemon=True).start()
                threading.Thread(target=pipe, args=(target_sock, client_sock), daemon=True).start()
            except Exception as e:
                print(f"Failed to connect to local tunnel endpoint on port {target_port}: {e}")
                client_sock.close()
    except KeyboardInterrupt:
        print("\nShutting down port forwarder.")
    finally:
        server.close()

if __name__ == '__main__':
    main()
