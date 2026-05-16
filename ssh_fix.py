#!/usr/bin/env python3
"""
LXC Container SSH Configurator v2
- Monitors for new containers
- Monitors database password changes
- Automatically updates containers when passwords change
- Shows passwords in UPPERCASE format
"""

import os
import sys
import json
import sqlite3
import subprocess
import logging
import threading
import time
import hashlib
from datetime import datetime
from pathlib import Path

# Configuration
DATABASE_PATH = '/opt/hvm/hvm.db'  # Your exact database path
CHECK_INTERVAL = 3  # Check every 3 seconds for faster response
DB_CHECK_INTERVAL = 5  # Check database for password changes every 5 seconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/lxc-ssh-configurator-v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ContainerMonitorV2:
    def __init__(self, db_path=None):
        self.db_path = db_path or DATABASE_PATH
        self.processed_containers = {}  # {container_name: password_hash}
        self.failed_containers = set()
        self.db_password_cache = {}  # {container_name: (password, last_updated)}
        self.running = True
        
        # Create state directory
        os.makedirs('/var/lib/lxc-ssh-configurator', exist_ok=True)
        
        # Load state
        self._load_state()
        
    def _load_state(self):
        """Load previously processed containers and password hashes"""
        state_file = '/var/lib/lxc-ssh-configurator/state.json'
        try:
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    self.processed_containers = data.get('processed', {})
                    self.failed_containers = set(data.get('failed', []))
                    logger.info(f"Loaded {len(self.processed_containers)} processed containers")
        except Exception as e:
            logger.warning(f"Could not load state file: {e}")
    
    def _save_state(self):
        """Save current state"""
        state_file = '/var/lib/lxc-ssh-configurator/state.json'
        try:
            with open(state_file, 'w') as f:
                json.dump({
                    'processed': self.processed_containers,
                    'failed': list(self.failed_containers)
                }, f)
        except Exception as e:
            logger.error(f"Could not save state file: {e}")
    
    def get_container_password_from_db(self, container_name):
        """Get container root password from database"""
        try:
            if not os.path.exists(self.db_path):
                logger.error(f"Database not found at {self.db_path}")
                return None
                
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Try multiple methods to get password
            password = None
            
            # Method 1: Direct root_password column
            cursor.execute("""
                SELECT root_password, metadata, status, container_name 
                FROM vps 
                WHERE container_name = ? OR hostname = ?
                LIMIT 1
            """, (container_name, container_name))
            
            row = cursor.fetchone()
            if row:
                # Check root_password column
                if row['root_password'] and row['root_password'] != 'root':
                    password = row['root_password']
                    logger.debug(f"Found password in root_password column for {container_name}")
                
                # Check metadata if not found
                if not password and row['metadata']:
                    try:
                        metadata = json.loads(row['metadata'])
                        if 'root_password' in metadata and metadata['root_password'] != 'root':
                            password = metadata['root_password']
                            logger.debug(f"Found password in metadata for {container_name}")
                    except:
                        pass
            
            conn.close()
            
            # If still no password, generate a strong one
            if not password:
                password = self.generate_strong_password()
                logger.info(f"Generated new strong password for {container_name}")
                # Update database with new password
                self.update_container_password_in_db(container_name, password)
            
            return password
            
        except Exception as e:
            logger.error(f"Error getting password from database: {e}")
            return self.generate_strong_password()
    
    def generate_strong_password(self, length=24):
        """Generate a strong random password"""
        import secrets
        import string
        chars = string.ascii_letters + string.digits + '!@#$%^&*'
        password = ''.join(secrets.choice(chars) for _ in range(length))
        return password
    
    def update_container_password_in_db(self, container_name, new_password):
        """Update container password in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update both root_password column and metadata
            cursor.execute("""
                UPDATE vps 
                SET root_password = ?, 
                    metadata = json_set(COALESCE(metadata, '{}'), '$.root_password', ?)
                WHERE container_name = ? OR hostname = ?
            """, (new_password, new_password, container_name, container_name))
            
            conn.commit()
            affected = cursor.rowcount
            conn.close()
            
            if affected > 0:
                logger.info(f"✅ Updated password in database for {container_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating password in database: {e}")
            return False
    
    def check_ssh_configured(self, container_name):
        """Check if SSH is already properly configured"""
        try:
            # Check if SSH config has PasswordAuthentication yes
            cmd = f"lxc exec {container_name} -- grep -q 'PasswordAuthentication yes' /etc/ssh/sshd_config 2>/dev/null && echo yes || echo no"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if 'yes' in result.stdout.lower():
                # Also check if we can get container status
                status_cmd = f"lxc info {container_name} --format=json 2>/dev/null | grep -q running && echo yes || echo no"
                status_result = subprocess.run(status_cmd, shell=True, capture_output=True, text=True, timeout=5)
                return True
            return False
        except Exception as e:
            logger.debug(f"SSH check failed: {e}")
            return False
    
    def configure_container_ssh(self, container_name, password):
        """Configure SSH and set root password for container"""
        try:
            logger.info(f"🔧 Configuring SSH for container: {container_name.upper()}")
            
            # Check if container exists and is running
            check_cmd = f"lxc info {container_name} 2>/dev/null | grep -q Status && echo exists || echo missing"
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if 'missing' in result.stdout.lower():
                logger.warning(f"Container {container_name} does not exist")
                return False
            
            # Write SSH config
            ssh_cmd = f"""lxc exec {container_name} -- bash -c 'cat > /etc/ssh/sshd_config << "EOF"
# SSH LOGIN SETTINGS
PasswordAuthentication yes
PermitRootLogin yes
PubkeyAuthentication no
ChallengeResponseAuthentication no
UsePAM yes

# SFTP SETTINGS
Subsystem sftp /usr/lib/openssh/sftp-server
EOF'"""
            
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                error_msg = result.stderr[:200]
                logger.error(f"Failed to write SSH config: {error_msg}")
                return False
            
            # Restart SSH service
            restart_cmd = f"lxc exec {container_name} -- bash -c 'systemctl restart ssh 2>/dev/null || service ssh restart 2>/dev/null || systemctl restart sshd 2>/dev/null || service sshd restart || true'"
            subprocess.run(restart_cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            # Set root password
            escaped_password = password.replace("'", "'\\''")
            passwd_cmd = f"lxc exec {container_name} -- bash -c \"echo 'root:{escaped_password}' | chpasswd\""
            result = subprocess.run(passwd_cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.error(f"Failed to set password: {result.stderr[:200]}")
                return False
            
            # Store password in container for future reference
            store_cmds = [
                f"lxc exec {container_name} -- bash -c \"echo '{escaped_password}' > /root/.hvm_password && chmod 600 /root/.hvm_password\"",
                f"lxc exec {container_name} -- bash -c \"mkdir -p /etc/hvm && echo '{escaped_password}' > /etc/hvm/password && chmod 600 /etc/hvm/password\"",
                f"lxc exec {container_name} -- bash -c \"echo 'root:{escaped_password}' > /root/.ssh/root_password && chmod 600 /root/.ssh/root_password 2>/dev/null || true\""
            ]
            
            for cmd in store_cmds:
                subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            # Display password in UPPERCASE
            password_upper = password.upper()
            logger.info(f"✅ SUCCESS! Container {container_name.upper()} configured with PASSWORD: {password_upper}")
            
            # Also print to console in a visible way
            print("\n" + "="*70)
            print(f"🔐 CONTAINER: {container_name.upper()}")
            print(f"🔑 PASSWORD: {password_upper}")
            print("="*70 + "\n")
            
            return True
            
        except subprocess.TimeoutError:
            logger.error(f"Timeout configuring SSH for {container_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to configure SSH: {e}")
            return False
    
    def get_running_containers(self):
        """Get list of running LXC containers"""
        try:
            result = subprocess.run(
                ['lxc', 'list', '--format=json'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return []
            
            containers = json.loads(result.stdout)
            running = []
            
            for container in containers:
                status = container.get('status', '').lower()
                name = container.get('name', '')
                
                if status == 'running':
                    running.append(name)
            
            return running
            
        except Exception as e:
            logger.error(f"Error getting container list: {e}")
            return []
    
    def monitor_database_changes(self):
        """Monitor database for password changes"""
        last_db_state = {}
        
        while self.running:
            try:
                if not os.path.exists(self.db_path):
                    time.sleep(DB_CHECK_INTERVAL)
                    continue
                
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get all VPS with their passwords
                cursor.execute("""
                    SELECT container_name, hostname, root_password, 
                           json_extract(metadata, '$.root_password') as meta_password,
                           status, updated_at
                    FROM vps
                    WHERE status = 'running' OR status = 'installing' OR status = 'reinstalling'
                """)
                
                rows = cursor.fetchall()
                conn.close()
                
                for row in rows:
                    container_name = row['container_name'] or row['hostname']
                    if not container_name:
                        continue
                    
                    # Get actual password (prefer root_password column)
                    password = row['root_password']
                    if not password or password == 'root':
                        password = row['meta_password']
                    
                    if password and password != 'root':
                        # Create a hash of the password to detect changes
                        password_hash = hashlib.md5(password.encode()).hexdigest()
                        
                        # Check if password changed
                        if container_name in self.processed_containers:
                            old_hash = self.processed_containers[container_name]
                            if old_hash != password_hash:
                                logger.info(f"🔄 Password changed for {container_name.upper()}! Applying new password...")
                                # Update container with new password
                                if self.configure_container_ssh(container_name, password):
                                    self.processed_containers[container_name] = password_hash
                                    self._save_state()
                        else:
                            # New container detected via database
                            if container_name not in self.failed_containers:
                                logger.info(f"📦 New container detected in DB: {container_name.upper()}")
                                if self.configure_container_ssh(container_name, password):
                                    self.processed_containers[container_name] = password_hash
                                    self._save_state()
                
                time.sleep(DB_CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error monitoring database: {e}")
                time.sleep(DB_CHECK_INTERVAL)
    
    def process_container(self, container_name):
        """Process a new container"""
        logger.info(f"📦 Processing container: {container_name.upper()}")
        
        # Wait a bit for container to be fully ready
        time.sleep(5)
        
        # Verify container is still running
        running = self.get_running_containers()
        if container_name not in running:
            logger.warning(f"Container {container_name} is not running, will retry")
            self.failed_containers.add(container_name)
            self._save_state()
            return
        
        # Get password
        password = self.get_container_password_from_db(container_name)
        
        if not password:
            logger.error(f"No password available for {container_name}")
            self.failed_containers.add(container_name)
            self._save_state()
            return
        
        # Configure SSH
        if self.configure_container_ssh(container_name, password):
            # Create password hash for tracking
            password_hash = hashlib.md5(password.encode()).hexdigest()
            self.processed_containers[container_name] = password_hash
            self.failed_containers.discard(container_name)
            self._save_state()
            logger.info(f"✅ Successfully configured {container_name.upper()}")
        else:
            logger.error(f"❌ Failed to configure {container_name.upper()}")
            self.failed_containers.add(container_name)
            self._save_state()
    
    def monitor_containers(self):
        """Monitor for new containers"""
        while self.running:
            try:
                running_containers = self.get_running_containers()
                
                for container in running_containers:
                    # Check if container needs processing
                    if container not in self.processed_containers and container not in self.failed_containers:
                        logger.info(f"🆕 New container detected: {container.upper()}")
                        
                        thread = threading.Thread(
                            target=self.process_container,
                            args=(container,)
                        )
                        thread.daemon = True
                        thread.start()
                
                time.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in container monitor: {e}")
                time.sleep(CHECK_INTERVAL)
    
    def run(self):
        """Main monitoring loop - runs both monitors"""
        logger.info("="*60)
        logger.info("🚀 LXC Container SSH Configurator V2 STARTED")
        logger.info(f"📁 Database: {self.db_path}")
        logger.info(f"⏱️  Container check interval: {CHECK_INTERVAL}s")
        logger.info(f"⏱️  Database check interval: {DB_CHECK_INTERVAL}s")
        logger.info("="*60)
        
        # Start both monitoring threads
        container_thread = threading.Thread(target=self.monitor_containers, daemon=True)
        db_thread = threading.Thread(target=self.monitor_database_changes, daemon=True)
        
        container_thread.start()
        db_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.running = False
            sys.exit(0)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='LXC Container SSH Configurator V2')
    parser.add_argument('--db-path', type=str, default=DATABASE_PATH,
                       help=f'Path to database (default: {DATABASE_PATH})')
    parser.add_argument('--test', type=str, metavar='CONTAINER',
                       help='Test configuration on a specific container (shows password in UPPERCASE)')
    parser.add_argument('--reset', action='store_true', 
                       help='Reset processed state')
    parser.add_argument('--force-update', type=str, metavar='CONTAINER',
                       help='Force update password for container from database')
    parser.add_argument('--list-passwords', action='store_true',
                       help='List all passwords from database (UPPERCASE)')
    
    args = parser.parse_args()
    
    monitor = ContainerMonitorV2(db_path=args.db_path)
    
    if args.reset:
        state_file = '/var/lib/lxc-ssh-configurator/state.json'
        if os.path.exists(state_file):
            os.remove(state_file)
            logger.info("✅ Reset processed state")
        return
    
    if args.list_passwords:
        try:
            conn = sqlite3.connect(args.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT container_name, hostname, root_password,
                       json_extract(metadata, '$.root_password') as meta_password
                FROM vps
                ORDER BY container_name
            """)
            rows = cursor.fetchall()
            conn.close()
            
            print("\n" + "="*70)
            print("📋 CONTAINER PASSWORDS (in UPPERCASE)")
            print("="*70)
            for row in rows:
                name = row['container_name'] or row['hostname'] or 'Unknown'
                password = row['root_password']
                if not password or password == 'root':
                    password = row['meta_password']
                if password and password != 'root':
                    print(f"🔐 {name.upper():30} -> {password.upper()}")
                else:
                    print(f"⚠️  {name.upper():30} -> (no password set / using 'root')")
            print("="*70 + "\n")
        except Exception as e:
            print(f"Error: {e}")
        return
    
    if args.test:
        print(f"\n🔧 Testing container: {args.test.upper()}")
        password = monitor.get_container_password_from_db(args.test)
        if password:
            monitor.configure_container_ssh(args.test, password)
            # Update database with the password we used
            monitor.update_container_password_in_db(args.test, password)
            print(f"\n✅ Container {args.test.upper()} configured!")
        else:
            print(f"❌ No password found for {args.test}")
        return
    
    if args.force_update:
        print(f"\n🔄 Force updating container: {args.force_update.upper()}")
        password = monitor.get_container_password_from_db(args.force_update)
        if password:
            # Remove from processed to force reconfiguration
            if args.force_update in monitor.processed_containers:
                del monitor.processed_containers[args.force_update]
            monitor.configure_container_ssh(args.force_update, password)
            print(f"\n✅ Container {args.force_update.upper()} updated!")
        else:
            print(f"❌ No password found for {args.force_update}")
        return
    
    # Normal monitoring mode
    monitor.run()

if __name__ == "__main__":
    main()
