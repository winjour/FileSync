# 电脑文件本地增量同步

import os
import shutil
import time
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from datetime import datetime
import queue

class FileSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("文件同步备份工具")
        self.root.geometry("900x600")
        self.root.minsize(800, 500)

        self.sync_queue = queue.Queue()
        self.syncing = False
        self.monitor_thread = None
        self.stop_monitor = False

        self.create_ui()
        self.start_queue_processor()

    def create_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 源文件夹和目标文件夹选择
        path_frame = ttk.LabelFrame(main_frame, text="文件夹设置", padding=10)
        path_frame.pack(fill=tk.X, pady=5)

        # 源文件夹
        ttk.Label(path_frame, text="源文件夹:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.source_var = tk.StringVar()
        source_entry = ttk.Entry(path_frame, textvariable=self.source_var, width=50)
        source_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(path_frame, text="浏览...", command=self.browse_source).grid(row=0, column=2, padx=5, pady=5)

        # 目标文件夹
        ttk.Label(path_frame, text="目标文件夹:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.dest_var = tk.StringVar()
        dest_entry = ttk.Entry(path_frame, textvariable=self.dest_var, width=50)
        dest_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        ttk.Button(path_frame, text="浏览...", command=self.browse_dest).grid(row=1, column=2, padx=5, pady=5)

        path_frame.columnconfigure(1, weight=1)

        # 同步选项
        options_frame = ttk.LabelFrame(main_frame, text="同步选项", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        # 实时监控选项
        self.monitor_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="实时监控源文件夹变化", variable=self.monitor_var,
                        command=self.toggle_monitor).pack(anchor=tk.W, padx=5, pady=5)

        # 操作按钮
        button_frame = ttk.Frame(main_frame, padding=5)
        button_frame.pack(fill=tk.X, pady=5)

        self.sync_button = ttk.Button(button_frame, text="立即同步", command=self.start_sync)
        self.sync_button.pack(side=tk.RIGHT, padx=5)

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="同步日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 创建Treeview显示日志
        self.log_tree = ttk.Treeview(log_frame, columns=("时间", "操作", "文件", "大小", "状态"), show="headings")
        self.log_tree.heading("时间", text="时间")
        self.log_tree.heading("操作", text="操作")
        self.log_tree.heading("文件", text="文件")
        self.log_tree.heading("大小", text="大小")
        self.log_tree.heading("状态", text="状态")

        self.log_tree.column("时间", width=150)
        self.log_tree.column("操作", width=80)
        self.log_tree.column("文件", width=400)
        self.log_tree.column("大小", width=100)
        self.log_tree.column("状态", width=100)

        scrollbar_y = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scrollbar_y.set)

        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)

    def browse_source(self):
        directory = filedialog.askdirectory()
        if directory:
            self.source_var.set(directory)

    def browse_dest(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dest_var.set(directory)

    def toggle_monitor(self):
        if self.monitor_var.get():
            # 开始监控
            if self.source_var.get() and os.path.isdir(self.source_var.get()):
                self.start_monitor()
            else:
                messagebox.showerror("错误", "请先选择有效的源文件夹")
                self.monitor_var.set(False)
        else:
            # 停止监控
            self.stop_monitor = True
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.status_var.set("正在停止监控...")

    def start_monitor(self):
        self.stop_monitor = False
        self.monitor_thread = threading.Thread(target=self.monitor_source_folder)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.status_var.set("正在监控源文件夹变化...")

    def monitor_source_folder(self):
        source_dir = self.source_var.get()
        last_states = self.get_folder_state(source_dir)

        try:
            while not self.stop_monitor:
                time.sleep(2)  # 每2秒检查一次变化
                current_states = self.get_folder_state(source_dir)

                # 检查文件变化
                for file_path, current_hash in current_states.items():
                    if file_path not in last_states:
                        # 新文件
                        self.sync_queue.put(('add', file_path))
                    elif current_hash != last_states[file_path]:
                        # 修改的文件
                        self.sync_queue.put(('update', file_path))

                # 检查删除的文件
                for file_path in last_states:
                    if file_path not in current_states:
                        self.sync_queue.put(('delete', file_path))

                last_states = current_states

            self.root.after(0, lambda: self.status_var.set("已停止监控"))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"监控错误: {str(e)}"))
            self.root.after(0, lambda: self.monitor_var.set(False))

    def get_folder_state(self, folder_path):
        """获取文件夹中所有文件的状态（路径和哈希值）"""
        states = {}
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_hash = self.get_file_hash(file_path)
                    rel_path = os.path.relpath(file_path, folder_path)
                    states[rel_path] = file_hash
                except:
                    pass  # 忽略无法读取的文件
        return states

    def get_file_hash(self, file_path):
        """计算文件的MD5哈希值"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def get_file_size(self, file_path):
        """获取文件大小并返回格式化的字符串"""
        try:
            size_bytes = os.path.getsize(file_path)
            # 格式化为人类可读的大小
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0 or unit == 'TB':
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
        except:
            return "未知"

    def start_queue_processor(self):
        """启动队列处理器线程"""
        threading.Thread(target=self.process_sync_queue, daemon=True).start()

    def process_sync_queue(self):
        """处理同步队列中的任务"""
        while True:
            try:
                if not self.syncing:
                    action, file_path = self.sync_queue.get(timeout=1)
                    self.sync_single_file(action, file_path)
                    self.sync_queue.task_done()
                else:
                    time.sleep(0.5)  # 如果正在进行全量同步，则等待
            except queue.Empty:
                time.sleep(0.5)  # 队列为空，稍等一会
            except Exception as e:
                print(f"处理队列错误: {e}")
                time.sleep(1)

    def sync_single_file(self, action, rel_path):
        """同步单个文件"""
        source_dir = self.source_var.get()
        dest_dir = self.dest_var.get()

        if not source_dir or not dest_dir:
            return

        source_path = os.path.join(source_dir, rel_path)
        dest_path = os.path.join(dest_dir, rel_path)
        file_size = "N/A"  # 默认值

        try:
            if action in ('add', 'update'):
                # 获取文件大小
                file_size = self.get_file_size(source_path)

                # 确保目标目录存在
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                # 复制文件
                shutil.copy2(source_path, dest_path)
                status = "成功"
            elif action == 'delete':
                # 对于删除操作，如果文件存在则获取大小
                if os.path.exists(dest_path) and os.path.isfile(dest_path):
                    file_size = self.get_file_size(dest_path)

                # 删除目标文件（如果存在）
                if os.path.exists(dest_path):
                    if os.path.isfile(dest_path):
                        os.remove(dest_path)
                    else:
                        shutil.rmtree(dest_path)
                status = "成功"

            # 更新日志
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            action_text = {"add": "新增", "update": "更新", "delete": "删除"}[action]

            self.root.after(0, lambda: self.log_tree.insert("", 0, values=(
            timestamp, action_text, rel_path, file_size, status)))
        except Exception as e:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            action_text = {"add": "新增", "update": "更新", "delete": "删除"}[action]
            self.root.after(0, lambda: self.log_tree.insert("", 0, values=(
            timestamp, action_text, rel_path, file_size, f"失败: {str(e)}")))

    def start_sync(self):
        """开始全量同步"""
        source_dir = self.source_var.get()
        dest_dir = self.dest_var.get()

        if not source_dir or not os.path.isdir(source_dir):
            messagebox.showerror("错误", "请选择有效的源文件夹")
            return

        if not dest_dir or not os.path.isdir(dest_dir):
            messagebox.showerror("错误", "请选择有效的目标文件夹")
            return

        if self.syncing:
            messagebox.showinfo("提示", "同步已在进行中")
            return

        if messagebox.askyesno("确认", "确定要开始同步吗？"):
            self.syncing = True
            self.sync_button.config(state=tk.DISABLED)
            self.status_var.set("正在同步...")

            # 在新线程中执行同步
            sync_thread = threading.Thread(target=self.perform_sync)
            sync_thread.daemon = True
            sync_thread.start()

    def perform_sync(self):
        """执行全量同步"""
        try:
            source_dir = self.source_var.get()
            dest_dir = self.dest_var.get()

            total_bytes = 0  # 记录总数据流量
            files_processed = 0  # 处理的文件数

            # 获取源文件夹和目标文件夹的状态
            source_states = self.get_folder_state(source_dir)
            dest_states = self.get_folder_state(dest_dir)

            # 处理新增和更新的文件
            for rel_path, src_hash in source_states.items():
                if rel_path not in dest_states or dest_states[rel_path] != src_hash:
                    source_path = os.path.join(source_dir, rel_path)
                    dest_path = os.path.join(dest_dir, rel_path)

                    # 获取文件大小
                    file_size_bytes = os.path.getsize(source_path)
                    file_size = self.get_file_size(source_path)
                    total_bytes += file_size_bytes
                    files_processed += 1

                    # 确保目标目录存在
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                    # 复制文件
                    shutil.copy2(source_path, dest_path)

                    # 更新日志
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    action = "更新" if rel_path in dest_states else "新增"
                    self.root.after(0, lambda t=timestamp, a=action, p=rel_path, s=file_size:
                    self.log_tree.insert("", 0, values=(t, a, p, s, "成功")))

            # 处理需要删除的文件
            for rel_path in dest_states:
                if rel_path not in source_states:
                    dest_path = os.path.join(dest_dir, rel_path)

                    # 获取文件大小（如果是文件）
                    file_size = "N/A"
                    if os.path.exists(dest_path) and os.path.isfile(dest_path):
                        file_size = self.get_file_size(dest_path)
                        files_processed += 1

                    if os.path.exists(dest_path):
                        if os.path.isfile(dest_path):
                            os.remove(dest_path)
                        else:
                            shutil.rmtree(dest_path)

                    # 更新日志
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.root.after(0, lambda t=timestamp, p=rel_path, s=file_size:
                    self.log_tree.insert("", 0, values=(t, "删除", p, s, "成功")))

            # 格式化总流量显示
            total_size_formatted = "0 B"
            size_bytes = total_bytes
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0 or unit == 'TB':
                    total_size_formatted = f"{size_bytes:.2f} {unit}"
                    break
                size_bytes /= 1024.0

            self.root.after(0, lambda: self.status_var.set(
                f"同步完成，共处理 {files_processed} 个文件，总数据量 {total_size_formatted}"))
            self.root.after(0, lambda: messagebox.showinfo("成功",
                                                           f"文件同步完成，共处理 {files_processed} 个文件，总数据量 {total_size_formatted}"))
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"同步错误: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"同步过程中发生错误: {str(e)}"))
        finally:
            self.syncing = False
            self.root.after(0, lambda: self.sync_button.config(state=tk.NORMAL))

if __name__ == "__main__":
    root = tk.Tk()
    app = FileSyncApp(root)
    root.mainloop()
