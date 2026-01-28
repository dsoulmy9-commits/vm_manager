import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import json
import threading
import time
import libvirt
import psutil

class VirtualMachineManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Python VirtualBox Clone")
        self.root.geometry("1200x700")
        
        # Store VM instances
        self.vms = {}
        self.load_vms()
        
        # Setup GUI
        self.setup_ui()
        
        # Connect to libvirt
        try:
            self.conn = libvirt.open('qemu:///system')
        except:
            self.conn = None
            messagebox.showwarning("Warning", "Could not connect to libvirt")
    
    def setup_ui(self):
        # Create main frames
        left_frame = tk.Frame(self.root, width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        main_frame = tk.Frame(self.root)
        main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - VM List
        tk.Label(left_frame, text="Virtual Machines", font=('Arial', 12, 'bold')).pack(pady=5)
        
        self.vm_listbox = tk.Listbox(left_frame, height=20)
        self.vm_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.vm_listbox.bind('<<ListboxSelect>>', self.on_vm_select)
        
        # Control buttons
        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        buttons = [
            ("New VM", self.create_vm),
            ("Start", self.start_vm),
            ("Stop", self.stop_vm),
            ("Pause", self.pause_vm),
            ("Delete", self.delete_vm),
            ("Settings", self.vm_settings)
        ]
        
        for text, command in buttons:
            btn = tk.Button(btn_frame, text=text, command=command, width=12)
            btn.pack(pady=2)
        
        # Right panel - Details and Console
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Details tab
        details_frame = tk.Frame(notebook)
        notebook.add(details_frame, text="Details")
        self.setup_details_tab(details_frame)
        
        # Console tab (simulated)
        console_frame = tk.Frame(notebook)
        notebook.add(console_frame, text="Console")
        self.setup_console_tab(console_frame)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = tk.Label(self.root, textvariable=self.status_var, 
                              bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.update_vm_list()
    
    def setup_details_tab(self, parent):
        # VM Details
        details_text = tk.Text(parent, height=20, width=60)
        details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.details_text = details_text
        
        # Progress bar for resources
        self.progress_frame = tk.Frame(parent)
        self.progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(self.progress_frame, text="CPU Usage:").grid(row=0, column=0, sticky=tk.W)
        self.cpu_bar = ttk.Progressbar(self.progress_frame, length=200)
        self.cpu_bar.grid(row=0, column=1, padx=5)
        
        tk.Label(self.progress_frame, text="Memory Usage:").grid(row=1, column=0, sticky=tk.W)
        self.mem_bar = ttk.Progressbar(self.progress_frame, length=200)
        self.mem_bar.grid(row=1, column=1, padx=5)
    
    def setup_console_tab(self, parent):
        # Simulated console output
        console_text = tk.Text(parent, height=25, width=80, bg='black', fg='green')
        console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        console_text.insert(tk.END, "Virtual Machine Console\n")
        console_text.insert(tk.END, "="*50 + "\n")
        self.console_text = console_text
    
    def create_vm(self):
        # Create new VM dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Virtual Machine")
        dialog.geometry("500x400")
        
        # VM Configuration inputs
        tk.Label(dialog, text="VM Name:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        name_entry = tk.Entry(dialog, width=30)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(dialog, text="Memory (MB):").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        mem_entry = tk.Entry(dialog, width=30)
        mem_entry.insert(0, "1024")
        mem_entry.grid(row=1, column=1, padx=5, pady=5)
        
        tk.Label(dialog, text="Disk Size (GB):").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        disk_entry = tk.Entry(dialog, width=30)
        disk_entry.insert(0, "20")
        disk_entry.grid(row=2, column=1, padx=5, pady=5)
        
        tk.Label(dialog, text="ISO Image:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        iso_path = tk.StringVar()
        tk.Entry(dialog, textvariable=iso_path, width=25).grid(row=3, column=1, padx=5, pady=5)
        tk.Button(dialog, text="Browse", command=lambda: iso_path.set(filedialog.askopenfilename(
            filetypes=[("ISO files", "*.iso"), ("All files", "*.*")]))).grid(row=3, column=2)
        
        def create():
            name = name_entry.get()
            memory = mem_entry.get()
            disk = disk_entry.get()
            iso = iso_path.get()
            
            if not name:
                messagebox.showerror("Error", "VM name is required")
                return
            
            vm_config = {
                'name': name,
                'memory': memory,
                'disk': disk,
                'iso': iso,
                'status': 'stopped',
                'pid': None
            }
            
            self.vms[name] = vm_config
            self.save_vms()
            self.update_vm_list()
            self.status_var.set(f"VM '{name}' created")
            dialog.destroy()
            
            # Create disk image
            self.create_disk_image(name, disk)
        
        tk.Button(dialog, text="Create", command=create).grid(row=4, column=1, pady=20)
    
    def create_disk_image(self, vm_name, size_gb):
        """Create QCOW2 disk image"""
        disk_path = f"./vms/{vm_name}/disk.qcow2"
        os.makedirs(f"./vms/{vm_name}", exist_ok=True)
        
        try:
            subprocess.run([
                'qemu-img', 'create', '-f', 'qcow2',
                disk_path, f'{size_gb}G'
            ], check=True)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create disk: {str(e)}")
            return False
    
    def start_vm(self):
        selection = self.vm_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a VM first")
            return
        
        vm_name = self.vm_listbox.get(selection[0])
        vm = self.vms.get(vm_name)
        
        if not vm:
            return
        
        # Start VM using QEMU
        iso_path = vm.get('iso', '')
        disk_path = f"./vms/{vm_name}/disk.qcow2"
        
        cmd = [
            'qemu-system-x86_64',
            '-enable-kvm',
            '-m', str(vm['memory']),
            '-hda', disk_path,
            '-cdrom', iso_path if iso_path else '',
            '-boot', 'd' if iso_path else 'c',
            '-vnc', ':0',
            '-daemonize'
        ]
        
        try:
            # Start in background thread
            thread = threading.Thread(target=self.run_vm_command, args=(cmd, vm_name))
            thread.daemon = True
            thread.start()
            
            vm['status'] = 'running'
            self.status_var.set(f"VM '{vm_name}' starting...")
            self.update_vm_list()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start VM: {str(e)}")
    
    def run_vm_command(self, cmd, vm_name):
        """Run VM command in background"""
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.vms[vm_name]['pid'] = process.pid
            self.console_text.insert(tk.END, f"\n[{time.ctime()}] VM '{vm_name}' started (PID: {process.pid})")
        except Exception as e:
            self.console_text.insert(tk.END, f"\nError: {str(e)}")
    
    def stop_vm(self):
        selection = self.vm_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a VM first")
            return
        
        vm_name = self.vm_listbox.get(selection[0])
        vm = self.vms.get(vm_name)
        
        if not vm or not vm.get('pid'):
            return
        
        try:
            # Send SIGTERM to stop VM
            os.kill(vm['pid'], 15)
            vm['status'] = 'stopped'
            vm['pid'] = None
            self.save_vms()
            self.update_vm_list()
            self.status_var.set(f"VM '{vm_name}' stopped")
            
            self.console_text.insert(tk.END, f"\n[{time.ctime()}] VM '{vm_name}' stopped")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop VM: {str(e)}")
    
    def pause_vm(self):
        selection = self.vm_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a VM first")
            return
        
        vm_name = self.vm_listbox.get(selection[0])
        vm = self.vms.get(vm_name)
        
        if not vm or not vm.get('pid'):
            return
        
        try:
            # Send SIGSTOP to pause
            os.kill(vm['pid'], 19)
            vm['status'] = 'paused'
            self.update_vm_list()
            self.status_var.set(f"VM '{vm_name}' paused")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to pause VM: {str(e)}")
    
    def delete_vm(self):
        selection = self.vm_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a VM first")
            return
        
        vm_name = self.vm_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirm", f"Delete VM '{vm_name}'?"):
            # Stop VM if running
            vm = self.vms.get(vm_name)
            if vm and vm.get('pid'):
                try:
                    os.kill(vm['pid'], 15)
                except:
                    pass
            
            # Remove from list
            del self.vms[vm_name]
            self.save_vms()
            self.update_vm_list()
            self.status_var.set(f"VM '{vm_name}' deleted")
    
    def vm_settings(self):
        selection = self.vm_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Select a VM first")
            return
        
        vm_name = self.vm_listbox.get(selection[0])
        vm = self.vms.get(vm_name)
        
        # Create settings dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Settings - {vm_name}")
        dialog.geometry("400x300")
        
        # Display current settings
        text = tk.Text(dialog, height=15, width=50)
        text.pack(padx=10, pady=10)
        
        settings_text = f"""VM Name: {vm['name']}
Memory: {vm['memory']} MB
Disk Size: {vm['disk']} GB
Status: {vm['status']}
ISO: {vm.get('iso', 'None')}
PID: {vm.get('pid', 'N/A')}
"""
        text.insert(tk.END, settings_text)
        text.config(state=tk.DISABLED)
    
    def on_vm_select(self, event):
        selection = self.vm_listbox.curselection()
        if not selection:
            return
        
        vm_name = self.vm_listbox.get(selection[0])
        vm = self.vms.get(vm_name)
        
        if vm:
            # Update details tab
            details = f"""Virtual Machine Details
{"="*30}
Name: {vm['name']}
Status: {vm['status']}
Memory: {vm['memory']} MB
Disk: {vm['disk']} GB
ISO: {vm.get('iso', 'Not set')}
PID: {vm.get('pid', 'N/A')}
"""
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, details)
            
            # Simulate resource usage (in real app, query VM stats)
            if vm['status'] == 'running':
                self.cpu_bar['value'] = 30
                self.mem_bar['value'] = 45
            else:
                self.cpu_bar['value'] = 0
                self.mem_bar['value'] = 0
    
    def update_vm_list(self):
        self.vm_listbox.delete(0, tk.END)
        for vm_name, vm_data in self.vms.items():
            status = vm_data.get('status', 'stopped')
            self.vm_listbox.insert(tk.END, f"{vm_name} [{status}]")
    
    def save_vms(self):
        """Save VM configurations to file"""
        os.makedirs('./vms', exist_ok=True)
        with open('./vms/vms.json', 'w') as f:
            json.dump(self.vms, f, indent=2)
    
    def load_vms(self):
        """Load VM configurations from file"""
        try:
            with open('./vms/vms.json', 'r') as f:
                self.vms = json.load(f)
        except FileNotFoundError:
            self.vms = {}
    
    def update_status(self):
        """Periodically update VM status"""
        for vm_name, vm in self.vms.items():
            if vm.get('pid'):
                try:
                    # Check if process is still running
                    os.kill(vm['pid'], 0)
                    vm['status'] = 'running'
                except OSError:
                    vm['status'] = 'stopped'
                    vm['pid'] = None
        
        self.update_vm_list()
        self.root.after(5000, self.update_status)

def main():
    root = tk.Tk()
    app = VirtualMachineManager(root)
    
    # Start status updates
    root.after(5000, app.update_status)
    
    root.mainloop()

if __name__ == "__main__":
    main()
