# 电脑文件本地增量同步v1.5
# 记忆上次同步设置和日志
# 仅贡献模式
# 可保存文件历史版本
# 增加文件历史版本管理器

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

        # 定时同步设置框架
        timer_frame = ttk.Frame(options_frame)
        timer_frame.pack(fill=tk.X, pady=5)

        # 定时同步复选框
        self.timer_var = tk.BooleanVar(value=False)
        timer_cb = ttk.Checkbutton(timer_frame, text="启用定时同步",
                                   variable=self.timer_var,
                                   command=self.toggle_timer)
        timer_cb.pack(side=tk.LEFT, padx=5)

        # 小时输入
        ttk.Label(timer_frame, text="间隔:").pack(side=tk.LEFT, padx=(15, 5))
        self.timer_hour = tk.StringVar(value="0")
        hour_entry = ttk.Entry(timer_frame, textvariable=self.timer_hour, width=3)
        hour_entry.pack(side=tk.LEFT)
        ttk.Label(timer_frame, text="小时").pack(side=tk.LEFT, padx=(0, 5))

        # 分钟输入
        self.timer_min = tk.StringVar(value="60")
        min_entry = ttk.Entry(timer_frame, textvariable=self.timer_min, width=3)
        min_entry.pack(side=tk.LEFT)
        ttk.Label(timer_frame, text="分钟").pack(side=tk.LEFT, padx=(0, 5))

        # 秒钟输入
        self.timer_sec = tk.StringVar(value="0")
        sec_entry = ttk.Entry(timer_frame, textvariable=self.timer_sec, width=3)
        sec_entry.pack(side=tk.LEFT)
        ttk.Label(timer_frame, text="秒").pack(side=tk.LEFT, padx=(0, 5))

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

        # 历史版本设置框架
        history_frame = ttk.Frame(options_frame)
        history_frame.pack(fill=tk.X, pady=5)

        # 历史版本管理复选框
        self.history_var = tk.BooleanVar(value=False)
        history_cb = ttk.Checkbutton(history_frame, text="保存文件历史版本",
                                    variable=self.history_var)
        history_cb.pack(side=tk.LEFT, padx=5)

        # 历史版本存储位置
        ttk.Label(history_frame, text="历史版本存储位置:").pack(side=tk.LEFT, padx=(15, 5))
        self.history_dir_var = tk.StringVar()
        history_entry = ttk.Entry(history_frame, textvariable=self.history_dir_var, width=30)
        history_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(history_frame, text="浏览...", command=self.browse_history_dir).pack(side=tk.LEFT, padx=5)

        # 最大历史版本数量
        history_max_frame = ttk.Frame(options_frame)
        history_max_frame.pack(fill=tk.X, pady=5)
        ttk.Label(history_max_frame, text="每个文件最大历史版本数量:").pack(side=tk.LEFT, padx=5)
        self.max_history_var = tk.StringVar(value="5")
        ttk.Entry(history_max_frame, textvariable=self.max_history_var, width=5).pack(side=tk.LEFT)
        ttk.Label(history_max_frame, text="(0表示不限制)").pack(side=tk.LEFT, padx=5)

        # 历史版本管理器按钮
        history_mgr_button = ttk.Button(history_max_frame, text="历史版本管理器",
                                        command=self.open_history_manager)
        history_mgr_button.pack(side=tk.RIGHT, padx=5)

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

                # 处理历史版本
                if self.history_var.get() and action == 'update' and os.path.exists(dest_path):
                    self.save_file_history(dest_path, rel_path)

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

            # 在新线程中执行同步，非静默模式
            sync_thread = threading.Thread(target=lambda: self.perform_sync(silent=False))
            sync_thread.daemon = True
            sync_thread.start()

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

        # 在新线程中执行同步，静默模式
        sync_thread = threading.Thread(target=lambda: self.perform_sync(silent=True))
        sync_thread.daemon = True
        sync_thread.start()

    def perform_sync(self, silent=False):
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

                    # 保存历史版本
                    if self.history_var.get() and rel_path in dest_states and os.path.exists(dest_path):
                        self.save_file_history(dest_path, rel_path)

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

            # 格式化总流量显示
            total_size_formatted = "0 B"
            size_bytes = total_bytes
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0 or unit == 'TB':
                    total_size_formatted = f"{size_bytes:.2f} {unit}"
                    break
                size_bytes /= 1024.0

            completion_message = f"同步完成，共处理 {files_processed} 个文件，总数据量 {total_size_formatted}"
            self.root.after(0, lambda: self.status_var.set(completion_message))

            # 只有在非静默模式下才显示弹窗
            if not silent:
                self.root.after(0, lambda: messagebox.showinfo("成功", completion_message))
        except Exception as e:
            error_message = f"同步错误: {str(e)}"
            self.root.after(0, lambda: self.status_var.set(error_message))
            # 只有在非静默模式下才显示错误弹窗
            if not silent:
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
            "timer_hour": self.timer_hour.get(),
            "timer_min": self.timer_min.get(),
            "timer_sec": self.timer_sec.get(),
            "history_enabled": self.history_var.get(),
            "history_dir": self.history_dir_var.get(),
            "max_history": self.max_history_var.get()
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

            # 加载定时器设置
            if "timer_hour" in settings:
                self.timer_hour.set(settings["timer_hour"])
            if "timer_min" in settings:
                self.timer_min.set(settings["timer_min"])
            if "timer_sec" in settings:
                self.timer_sec.set(settings["timer_sec"])

            # 加载历史版本设置
            if "history_enabled" in settings:
                self.history_var.set(settings["history_enabled"])
            if "history_dir" in settings:
                self.history_dir_var.set(settings["history_dir"])
            if "max_history" in settings:
                self.max_history_var.set(settings["max_history"])

            if "monitor_enabled" in settings:
                self.monitor_var.set(settings["monitor_enabled"])
                if settings["monitor_enabled"] and self.source_var.get():
                    # 延迟启动监控，确保UI已完全加载
                    self.root.after(1000, self.toggle_monitor)
                    # 设置监控状态显示
                    self.monitor_status_var.set("正在监控中...")
                    self.monitor_status.config(foreground="green")

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
                hours = int(self.timer_hour.get())
                minutes = int(self.timer_min.get())
                seconds = int(self.timer_sec.get())

                # 确保至少有一个值大于0
                if hours <= 0 and minutes <= 0 and seconds <= 0:
                    raise ValueError("至少需要设置一个大于0的时间间隔")

                # 计算总秒数
                total_seconds = hours * 3600 + minutes * 60 + seconds

                # 启动定时器
                self.start_timer(total_seconds)
                self.next_sync_label.config(foreground="green")
            except ValueError as e:
                messagebox.showerror("错误", f"请输入有效的时间间隔: {str(e)}")
                self.timer_var.set(False)
        else:
            # 停止定时器
            self.stop_timer()
            self.next_sync_var.set("")
            self.next_sync_label.config(foreground="gray")

    def start_timer(self, total_seconds):
        """启动定时器"""
        # 取消现有的定时器
        if hasattr(self, 'timer_id') and self.timer_id:
            self.root.after_cancel(self.timer_id)

        # 计算下次同步时间
        interval_ms = total_seconds * 1000  # 转换为毫秒
        next_time = datetime.now() + timedelta(seconds=total_seconds)
        self.next_sync_var.set(f"下次同步: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 设置新的定时器
        self.timer_id = self.root.after(interval_ms, self.timer_sync)

    def stop_timer(self):
        """停止定时器"""
        if hasattr(self, 'timer_id') and self.timer_id:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None
            self.next_sync_var.set("")
            self.next_sync_label.config(foreground="gray")

    def timer_sync(self):
        """定时器触发的同步操作"""
        if not self.syncing and self.source_var.get() and self.dest_var.get():
            # 执行同步，不需要用户确认
            self.silent_sync()

        # 如果定时器仍然启用，则设置下一次定时器
        if self.timer_var.get():
            hours = int(self.timer_hour.get())
            minutes = int(self.timer_min.get())
            seconds = int(self.timer_sec.get())
            total_seconds = hours * 3600 + minutes * 60 + seconds
            self.start_timer(total_seconds)

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

    def browse_history_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.history_dir_var.set(directory)

    def save_file_history(self, file_path, rel_path):
        """保存文件的历史版本"""
        try:
            history_dir = self.history_dir_var.get()
            if not history_dir or not os.path.isdir(history_dir):
                # 如果未设置历史目录或目录无效，则使用默认目录
                history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_versions")

            # 确保历史版本根目录存在
            os.makedirs(history_dir, exist_ok=True)

            # 创建文件对应的历史版本子目录
            file_history_dir = os.path.join(history_dir, os.path.dirname(rel_path))
            os.makedirs(file_history_dir, exist_ok=True)

            # 文件名加上时间戳作为历史版本文件名
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_filename = f"{os.path.splitext(filename)[0]}_{timestamp}{os.path.splitext(filename)[1]}"
            history_path = os.path.join(file_history_dir, history_filename)

            # 复制当前文件作为历史版本
            shutil.copy2(file_path, history_path)

            # 检查是否需要限制历史版本数量
            self.clean_old_history_versions(file_history_dir, filename)

            return True
        except Exception as e:
            print(f"保存历史版本失败: {e}")
            return False

    def clean_old_history_versions(self, history_dir, filename):
        """清理旧的历史版本，保持历史版本数量在限制范围内"""
        try:
            max_versions = int(self.max_history_var.get())
            if max_versions <= 0:  # 0表示不限制
                return

            # 获取文件名前缀
            name_prefix = os.path.splitext(filename)[0]
            ext = os.path.splitext(filename)[1]

            # 获取所有该文件的历史版本
            history_files = []
            for f in os.listdir(history_dir):
                if f.startswith(name_prefix + "_") and f.endswith(ext):
                    file_path = os.path.join(history_dir, f)
                    history_files.append((file_path, os.path.getmtime(file_path)))

            # 按修改时间排序
            history_files.sort(key=lambda x: x[1], reverse=True)

            # 删除超出限制的旧版本
            if len(history_files) > max_versions:
                for file_path, _ in history_files[max_versions:]:
                    os.remove(file_path)
        except Exception as e:
            print(f"清理旧历史版本失败: {e}")

    def open_history_manager(self):
        """打开历史版本管理器窗口"""
        # 检查历史版本目录是否有效
        history_dir = self.history_dir_var.get()
        if not history_dir or not os.path.isdir(history_dir):
            # 如果未设置历史目录或目录无效，则使用默认目录
            history_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_versions")
            if not os.path.exists(history_dir):
                messagebox.showinfo("提示", "历史版本目录不存在或尚无历史版本记录")
                return

        # 创建历史版本管理器窗口
        history_win = tk.Toplevel(self.root)
        history_win.title("历史版本管理器")
        history_win.geometry("900x600")
        history_win.minsize(800, 500)

        # 分割窗口为左右两部分
        paned = ttk.PanedWindow(history_win, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧文件树区域
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="文件结构:").pack(anchor=tk.W, pady=(0, 5))

        # 创建带滚动条的文件树
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.history_tree = ttk.Treeview(tree_frame, columns=("path",), show="tree")
        scrollbar_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.history_tree.xview)
        self.history_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 右侧版本列表区域
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        ttk.Label(right_frame, text="历史版本:").pack(anchor=tk.W, pady=(0, 5))

        # 创建版本列表
        versions_frame = ttk.Frame(right_frame)
        versions_frame.pack(fill=tk.BOTH, expand=True)

        self.versions_list = ttk.Treeview(versions_frame,
                                          columns=("版本", "日期", "大小"),
                                          show="headings")
        self.versions_list.heading("版本", text="版本")
        self.versions_list.heading("日期", text="日期")
        self.versions_list.heading("大小", text="大小")

        self.versions_list.column("版本", width=200)
        self.versions_list.column("日期", width=150)
        self.versions_list.column("大小", width=100)

        v_scrollbar_y = ttk.Scrollbar(versions_frame, orient=tk.VERTICAL, command=self.versions_list.yview)
        self.versions_list.configure(yscrollcommand=v_scrollbar_y.set)

        self.versions_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        # 操作按钮区域
        action_frame = ttk.Frame(right_frame)
        action_frame.pack(fill=tk.X, pady=10)

        ttk.Button(action_frame, text="恢复此版本",
                   command=lambda: self.restore_version(history_dir)).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="删除此版本",
                   command=lambda: self.delete_version(history_dir)).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="查看此版本",
                   command=lambda: self.view_version()).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="刷新",
                   command=lambda: self.load_history_tree(history_dir)).pack(side=tk.RIGHT, padx=5)

        # 状态栏
        status_var = tk.StringVar(value="选择一个文件以查看其历史版本")
        ttk.Label(history_win, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, side=tk.BOTTOM,
                                                                                            padx=5, pady=2)

        # 绑定事件
        self.history_tree.bind("<<TreeviewSelect>>", lambda e: self.on_file_selected(history_dir))
        self.versions_list.bind("<Double-1>", lambda e: self.view_version())

        # 加载文件树
        self.load_history_tree(history_dir)

    def load_history_tree(self, history_dir):
        """加载历史版本文件树"""
        # 清空当前树
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # 创建根节点
        root_id = self.history_tree.insert("", "end", text="历史版本根目录", open=True)

        # 递归加载目录结构
        self._load_directory(history_dir, root_id, history_dir)

    def _load_directory(self, dir_path, parent_node, base_dir):
        """递归加载目录结构"""
        try:
            # 按字母顺序排序，目录在前，文件在后
            items = sorted(os.listdir(dir_path))
            dirs = [item for item in items if os.path.isdir(os.path.join(dir_path, item))]
            files = [item for item in items if os.path.isfile(os.path.join(dir_path, item))]

            # 处理所有子目录
            for d in dirs:
                dir_full_path = os.path.join(dir_path, d)
                dir_rel_path = os.path.relpath(dir_full_path, base_dir)

                # 仅当目录包含历史版本文件时才添加到树中
                if self._has_history_files(dir_full_path):
                    node_id = self.history_tree.insert(parent_node, "end", text=d,
                                                      values=(dir_rel_path,), open=False)
                    self._load_directory(dir_full_path, node_id, base_dir)

            # 处理目录下的文件
            file_groups = self._group_history_files(files)
            for original_name in file_groups:
                if file_groups[original_name]:  # 只显示有历史版本的文件
                    file_rel_path = os.path.join(os.path.relpath(dir_path, base_dir), original_name)
                    self.history_tree.insert(parent_node, "end", text=original_name,
                                            values=(file_rel_path,), tags=("file",))
        except Exception as e:
            print(f"加载目录失败: {e}")

    def _has_history_files(self, dir_path):
        """检查目录是否包含历史版本文件（直接或间接）"""
        try:
            # 检查当前目录
            files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
            file_groups = self._group_history_files(files)
            if file_groups:  # 如果有任何分组，返回True
                return True

            # 检查子目录
            for d in [d for d in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, d))]:
                if self._has_history_files(os.path.join(dir_path, d)):
                    return True

            return False
        except Exception as e:
            print(f"检查历史文件失败: {e}")
            return False

    def _group_history_files(self, files):
        """将历史版本文件按原始文件名分组"""
        file_groups = {}
        for filename in files:
            # 尝试识别历史版本格式：name_20240605_123045.ext
            parts = filename.rsplit('_', 2)  # 从右侧分割，最多分割2次
            if len(parts) >= 3:
                # 检查倒数第二部分是否是日期格式
                date_part = parts[-2]
                if len(date_part) == 8 and date_part.isdigit():
                    # 检查倒数第一部分是否是时间格式
                    time_part = os.path.splitext(parts[-1])[0]
                    if len(time_part) == 6 and time_part.isdigit():
                        # 是历史版本文件
                        base_name = parts[0]
                        file_ext = os.path.splitext(filename)[1]
                        original_name = base_name + file_ext
                        if original_name not in file_groups:
                            file_groups[original_name] = []
                        file_groups[original_name].append(filename)

        return file_groups

    def on_file_selected(self, history_dir):
        """当在文件树中选择文件时显示其历史版本"""
        selected = self.history_tree.selection()
        if not selected:
            return

        # 清空版本列表
        for item in self.versions_list.get_children():
            self.versions_list.delete(item)

        item_id = selected[0]
        item_values = self.history_tree.item(item_id, "values")

        if not item_values:
            return

        rel_path = item_values[0]
        full_path = os.path.join(history_dir, rel_path)

        # 检查是否为文件
        if not os.path.isdir(full_path):
            # 获取目录和文件名
            dir_path = os.path.dirname(full_path)
            filename = os.path.basename(full_path)

            # 加载历史版本
            self.load_file_versions(dir_path, filename)

    def load_file_versions(self, dir_path, filename):
        """加载文件的历史版本列表"""
        try:
            # 获取文件名的基本部分和扩展名
            name_base, ext = os.path.splitext(filename)

            # 查找该文件的所有历史版本
            versions = []
            for f in os.listdir(dir_path):
                # 检查是否是该文件的历史版本
                if f.startswith(name_base + "_") and f.endswith(ext):
                    parts = f.rsplit('_', 2)  # 从右侧分割，最多分割2次
                    if len(parts) >= 3:
                        date_part = parts[-2]
                        time_part = os.path.splitext(parts[-1])[0]

                        if len(date_part) == 8 and date_part.isdigit() and len(time_part) == 6 and time_part.isdigit():
                            # 格式化日期和时间
                            date_formatted = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]}"
                            time_formatted = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
                            datetime_str = f"{date_formatted} {time_formatted}"

                            # 获取文件大小
                            file_path = os.path.join(dir_path, f)
                            file_size = self.get_file_size(file_path)

                            versions.append((f, datetime_str, file_size, file_path))

            # 按时间从新到旧排序
            versions.sort(key=lambda x: x[1], reverse=True)

            # 显示在版本列表中
            for version, datetime_str, size, path in versions:
                self.versions_list.insert("", "end", values=(version, datetime_str, size), tags=(path,))

        except Exception as e:
            print(f"加载文件版本失败: {e}")

    def view_version(self):
        """查看所选历史版本"""
        selected = self.versions_list.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择一个历史版本")
            return

        item_id = selected[0]
        file_path = self.versions_list.item(item_id, "tags")[0]

        try:
            # 使用系统默认程序打开文件
            os.startfile(file_path)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开文件: {str(e)}")

    def restore_version(self, history_dir):
        """恢复所选历史版本到源文件夹"""
        selected_tree = self.history_tree.selection()
        selected_version = self.versions_list.selection()

        if not selected_tree or not selected_version:
            messagebox.showinfo("提示", "请先选择一个文件和历史版本")
            return

        tree_item = selected_tree[0]
        version_item = selected_version[0]

        # 获取相对路径和历史版本文件路径
        rel_path = self.history_tree.item(tree_item, "values")[0]
        history_file_path = self.versions_list.item(version_item, "tags")[0]

        # 询问用户确认
        if not messagebox.askyesno("确认", "确定要恢复此历史版本吗？当前版本将被覆盖。"):
            return

        try:
            # 确定源文件夹路径
            source_dir = self.source_var.get()
            if not source_dir:
                messagebox.showerror("错误", "未设置源文件夹")
                return

            # 计算目标文件路径
            filename = os.path.basename(rel_path)
            target_dir = os.path.dirname(os.path.join(source_dir, rel_path))
            target_path = os.path.join(target_dir, filename)

            # 确保目标目录存在
            os.makedirs(target_dir, exist_ok=True)

            # 复制历史版本到目标路径
            shutil.copy2(history_file_path, target_path)

            messagebox.showinfo("成功", "历史版本已成功恢复")

            # 如果正在监控，会自动触发同步
        except Exception as e:
            messagebox.showerror("错误", f"恢复历史版本失败: {str(e)}")

    def delete_version(self, history_dir):
        """删除所选历史版本"""
        selected = self.versions_list.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择一个历史版本")
            return

        if not messagebox.askyesno("确认", "确定要删除此历史版本吗？此操作不可恢复。"):
            return

        try:
            for item_id in selected:
                file_path = self.versions_list.item(item_id, "tags")[0]
                os.remove(file_path)
                self.versions_list.delete(item_id)

            # 重新加载文件树以更新显示
            self.load_history_tree(history_dir)

            messagebox.showinfo("成功", "历史版本已成功删除")
        except Exception as e:
            messagebox.showerror("错误", f"删除历史版本失败: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FileSyncApp(root)
    root.mainloop()
