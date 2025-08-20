# 电脑文件本地增量同步v1.4
# 记忆上次同步设置和日志
# 仅贡献模式
# 增加定时同步

import os
import shutil
import time
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from datetime import datetime
import queue
import json
from datetime import datetime, timedelta

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

        # 加载保存的设置和历史
        self.load_settings()
        self.load_sync_history()

        # 设置窗口关闭时的操作
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.start_queue_processor()

    def on_closing(self):
        """窗口关闭时保存设置和历史"""
        # 停止监控线程
        if self.monitor_var.get():
            self.stop_monitor = True

        # 停止定时器
        self.stop_timer()

        # 保存设置和历史
        self.save_settings()
        self.save_sync_history()

        # 关闭窗口
        self.root.destroy()

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
        timer_frame = ttk.Frame(options_frame) #定时同步设置
        timer_frame.pack(fill=tk.X, pady=5)

        # 定时同步复选框
        self.timer_var = tk.BooleanVar(value=False)
        timer_cb = ttk.Checkbutton(timer_frame, text="启用定时同步",
                                   variable=self.timer_var,
                                   command=self.toggle_timer)
        timer_cb.pack(side=tk.LEFT, padx=5)

        # 定时间隔输入框
        ttk.Label(timer_frame, text="间隔:").pack(side=tk.LEFT, padx=(15, 5))
        self.timer_interval = tk.StringVar(value="60")
        interval_entry = ttk.Entry(timer_frame, textvariable=self.timer_interval, width=5)
        interval_entry.pack(side=tk.LEFT)
        ttk.Label(timer_frame, text="分钟").pack(side=tk.LEFT, padx=5)

        # 下次同步时间显示
        self.next_sync_var = tk.StringVar(value="")
        self.next_sync_label = ttk.Label(timer_frame, textvariable=self.next_sync_var,
                                         foreground="gray")
        self.next_sync_label.pack(side=tk.LEFT, padx=10)

        # 移除模式选择，添加模式说明
        mode_info = ttk.Label(options_frame,
                              text="贡献模式: 仅同步新增和修改的文件，不会删除目标文件夹中的文件",
                              justify=tk.LEFT)
        mode_info.pack(anchor=tk.W, padx=5, pady=5)

        # 实时监控选项和状态显示
        monitor_frame = ttk.Frame(options_frame)
        monitor_frame.pack(fill=tk.X, pady=5)

        # 监控复选框
        self.monitor_var = tk.BooleanVar(value=False)
        monitor_cb = ttk.Checkbutton(monitor_frame, text="实时监控源文件夹变化",
                                     variable=self.monitor_var,
                                     command=self.toggle_monitor)
        monitor_cb.pack(side=tk.LEFT, padx=5)

        # 监控状态标签
        self.monitor_status_var = tk.StringVar(value="")
        self.monitor_status = ttk.Label(monitor_frame, textvariable=self.monitor_status_var,
                                        foreground="gray")
        self.monitor_status.pack(side=tk.LEFT, padx=10)
        # 操作按钮
        button_frame = ttk.Frame(main_frame, padding=5)
        button_frame.pack(fill=tk.X, pady=5)

        self.sync_button = ttk.Button(button_frame, text="立即同步", command=self.start_sync)
        self.sync_button.pack(side=tk.RIGHT, padx=5)

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="同步日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 创建Treeview显示日志 - 先创建log_tree
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

        # 再创建清空历史按钮
        log_button_frame = ttk.Frame(log_frame)
        log_button_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(log_button_frame, text="清空历史", command=self.clear_history).pack(side=tk.RIGHT)

        scrollbar_y = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=scrollbar_y.set)

        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X,
                                                                                               side=tk.BOTTOM, padx=5,
                                                                                               pady=2)
    def clear_history(self):
        """清空同步历史记录"""
        if messagebox.askyesno("确认", "确定要清空同步历史记录吗？"):
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)
            self.save_sync_history()

    def browse_source(self):
        directory = filedialog.askdirectory()
        if directory:
            self.source_var.set(directory)

    def browse_dest(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dest_var.set(directory)

    def toggle_monitor(self):
        print(f"切换监控状态: {self.monitor_var.get()}")  # 调试信息
        if self.monitor_var.get():
            # 开始监控
            if self.source_var.get() and os.path.isdir(self.source_var.get()):
                self.start_monitor()
                print("开始监控")  # 调试信息
            else:
                messagebox.showerror("错误", "请先选择有效的源文件夹")
                self.monitor_var.set(False)
        else:
            # 停止监控
            self.stop_monitor = True
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_status_var.set("正在停止监控...")
                print("停止监控")  # 调试信息

    def start_monitor(self):
        self.stop_monitor = False
        self.monitor_thread = threading.Thread(target=self.monitor_source_folder)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.monitor_status_var.set("正在监控中...")
        self.monitor_status.config(foreground="green")

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

            self.root.after(0, lambda: self.monitor_status_var.set("已停止"))
            self.root.after(0, lambda: self.monitor_status.config(foreground="gray"))
        except Exception as e:
            self.root.after(0, lambda: self.monitor_status_var.set(f"监控错误: {str(e)}"))
            self.root.after(0, lambda: self.monitor_status.config(foreground="red"))
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

        # 在贡献模式下忽略删除操作
        if action == 'delete':
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
        self.save_sync_history()

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

            # 删除处理部分已移除

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
            self.root.after(0, self.save_sync_history)

    def save_settings(self):
        """保存当前设置到配置文件"""
        settings = {
            "source_dir": self.source_var.get(),
            "dest_dir": self.dest_var.get(),
            "monitor_enabled": self.monitor_var.get(),
            "timer_enabled": self.timer_var.get(),
            "timer_interval": self.timer_interval.get()
        }

        try:
            with open("sync_settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败: {e}")

    def load_settings(self):
        """从配置文件加载设置"""
        try:
            with open("sync_settings.json", "r", encoding="utf-8") as f:
                settings = json.load(f)

            if "source_dir" in settings and os.path.isdir(settings["source_dir"]):
                self.source_var.set(settings["source_dir"])

            if "dest_dir" in settings and os.path.isdir(settings["dest_dir"]):
                self.dest_var.set(settings["dest_dir"])

            if "monitor_enabled" in settings:
                self.monitor_var.set(settings["monitor_enabled"])
                if settings["monitor_enabled"] and self.source_var.get():
                    # 延迟启动监控，确保UI已完全加载
                    self.root.after(1000, self.toggle_monitor)
                    # 设置监控状态显示
                    self.monitor_status_var.set("正在监控中...")
                    self.monitor_status.config(foreground="green")

            if "timer_interval" in settings:
                self.timer_interval.set(settings["timer_interval"])

            if "timer_enabled" in settings and settings["timer_enabled"]:
                self.timer_var.set(True)
                # 延迟启动定时器，确保UI已完全加载
                self.root.after(1500, self.toggle_timer)
        except FileNotFoundError:
            # 配置文件不存在，使用默认值
            pass
        except Exception as e:
            print(f"加载设置失败: {e}")

    def load_sync_history(self):
        """从历史文件加载同步日志"""
        try:
            with open("sync_history.json", "r", encoding="utf-8") as f:
                history = json.load(f)

            # 清除现有日志
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)

            # 加载历史记录
            for log_entry in history:
                self.log_tree.insert("", 0, values=(
                    log_entry["时间"],
                    log_entry["操作"],
                    log_entry["文件"],
                    log_entry["大小"],
                    log_entry["状态"]
                ))
        except FileNotFoundError:
            # 历史文件不存在，忽略错误
            pass
        except Exception as e:
            print(f"加载同步历史失败: {e}")

    def save_sync_history(self):
        """保存同步日志到历史文件"""
        try:
            history = []
            for item_id in self.log_tree.get_children():
                values = self.log_tree.item(item_id, "values")
                history.append({
                    "时间": values[0],
                    "操作": values[1],
                    "文件": values[2],
                    "大小": values[3],
                    "状态": values[4]
                })

            with open("sync_history.json", "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存同步历史失败: {e}")

    def toggle_timer(self):
        """切换定时同步状态"""
        if self.timer_var.get():
            try:
                # 检查间隔设置是否有效
                interval = int(self.timer_interval.get())
                if interval <= 0:
                    raise ValueError("间隔必须大于0")

                # 启动定时器
                self.start_timer(interval)
                self.next_sync_label.config(foreground="green")
            except ValueError as e:
                messagebox.showerror("错误", f"请输入有效的时间间隔: {str(e)}")
                self.timer_var.set(False)
        else:
            # 停止定时器
            self.stop_timer()
            self.next_sync_var.set("")
            self.next_sync_label.config(foreground="gray")

    def start_timer(self, interval):
        """启动定时器"""
        # 取消现有的定时器
        if hasattr(self, 'timer_id') and self.timer_id:
            self.root.after_cancel(self.timer_id)

        # 计算下次同步时间
        interval_ms = interval * 60 * 1000  # 转换为毫秒
        next_time = datetime.now() + timedelta(minutes=interval)
        self.next_sync_var.set(f"下次同步: {next_time.strftime('%H:%M:%S')}")

        # 设置新的定时器
        self.timer_id = self.root.after(interval_ms, self.timer_sync)

    def stop_timer(self):
        """停止定时器"""
        if hasattr(self, 'timer_id') and self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

    def timer_sync(self):
        """定时器触发的同步操作"""
        if not self.syncing and self.source_var.get() and self.dest_var.get():
            # 执行同步，不需要用户确认
            self.silent_sync()

        # 如果定时器仍然启用，则设置下一次定时器
        if self.timer_var.get():
            interval = int(self.timer_interval.get())
            self.start_timer(interval)

    def silent_sync(self):
        """执行同步而不弹出确认对话框"""
        # 检查源目录和目标目录是否有效
        source_dir = self.source_var.get()
        dest_dir = self.dest_var.get()

        if not source_dir or not os.path.isdir(source_dir):
            self.status_var.set("错误: 源文件夹无效")
            return

        if not dest_dir or not os.path.isdir(dest_dir):
            self.status_var.set("错误: 目标文件夹无效")
            return

        if self.syncing:
            return

        # 开始同步
        self.syncing = True
        self.sync_button.config(state=tk.DISABLED)
        self.status_var.set("定时同步开始...")

        # 在新线程中执行同步
        sync_thread = threading.Thread(target=self.perform_sync)
        sync_thread.daemon = True
        sync_thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = FileSyncApp(root)
    root.mainloop()
