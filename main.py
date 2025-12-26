import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
import sys
import logging
import queue
import bot
from settings_ui import SettingsFrame
from single_instance import SingleInstance
import os
import json

class TextHandler(logging.Handler):
    """Logging handler that writes to a Queue (thread-safe)."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)


class MainGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Kiwoom Auto Trading Bot (GUI)")
        
        # Center Window (화면 크기 확대 반영)
        width, height = 1200, 900
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Prevent multiple instances
        self.lockfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui.lock')
        self.si = SingleInstance(self.lockfile)

        # [Thread-Safe Logging] Create a queue for logs
        self.log_queue = queue.Queue()

        # Style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Dashboard
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="📊 대시보드 (Dashboard)")
        self.setup_dashboard()
        
        # Tab 2: Settings
        self.settings_frame = SettingsFrame(self.notebook)
        self.notebook.add(self.settings_frame, text="⚙️ 환경설정 (Settings)")

        # Tab 3: Sell History
        self.sell_history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sell_history_frame, text="📜 매도내역 (Sell History)")
        self.setup_sell_history()
        
        # Bot Control
        self.bot_thread = None
        self.stop_event = asyncio.Event()
        self.loop = None
        self.bot_app = None
        
        # Start UI Auto Refresh
        self.auto_refresh_holdings()
        
        # [Force Auto-Start] 지체 없이 즉시 시작 (0.1초)
        print("[DEBUG] Forcing auto-start IMMEDIATELY...")
        self.root.after(100, self.start_bot)

    def setup_dashboard(self):
        # 1. Top Control Panel
        control_frame = ttk.LabelFrame(self.dashboard_frame, text="🤖 로봇 제어 (Control)", padding="10")
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_start = ttk.Button(control_frame, text="▶ 봇 시작 (START)", command=self.start_bot)
        self.btn_start.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.btn_stop = ttk.Button(control_frame, text="⏹ 봇 정지 (STOP)", command=self.stop_bot, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.lbl_status = ttk.Label(control_frame, text="상태: 정지됨 (Stopped)", foreground="red", font=("Arial", 10, "bold"))
        self.lbl_status.pack(side=tk.LEFT, padx=10)


        # 2. Account Summary Panel
        self.create_summary_view()

        # 3. Logs Panel (Bottom)
        log_frame = ttk.LabelFrame(self.dashboard_frame, text="📝 시스템 로그 (Logs)", padding="5")
        log_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=10, pady=5)
        # Fixed height for logs
        self.log_text = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.setup_logging()

        # 4. Holdings Panel (Middle)
        self.create_holdings_view()

    def create_summary_view(self):
        frame = ttk.LabelFrame(self.dashboard_frame, text="💰 계좌 자산 현황 (Account Status)", padding="10")
        frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Variables
        self.var_total_asset = tk.StringVar(value="0 원")
        self.var_total_buy = tk.StringVar(value="0 원")
        self.var_deposit = tk.StringVar(value="0 원")
        self.var_total_pl = tk.StringVar(value="0 원")
        self.var_yield = tk.StringVar(value="0.00 %")
        
        # Layout
        ttk.Label(frame, text="총 자산:").grid(row=0, column=0, sticky="e", padx=5)
        ttk.Label(frame, textvariable=self.var_total_asset, font=("Arial", 10, "bold")).grid(row=0, column=1, sticky="w", padx=15)
        
        ttk.Label(frame, text="총 매입:").grid(row=0, column=2, sticky="e", padx=5)
        ttk.Label(frame, textvariable=self.var_total_buy).grid(row=0, column=3, sticky="w", padx=15)
        
        ttk.Label(frame, text="예수금:").grid(row=0, column=4, sticky="e", padx=5)
        ttk.Label(frame, textvariable=self.var_deposit).grid(row=0, column=5, sticky="w", padx=15)
        
        ttk.Label(frame, text="총 손익:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.lbl_pl = ttk.Label(frame, textvariable=self.var_total_pl, font=("Arial", 10, "bold"))
        self.lbl_pl.grid(row=1, column=1, sticky="w", padx=15, pady=5)
        
        ttk.Label(frame, text="수익률:").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.lbl_yield = ttk.Label(frame, textvariable=self.var_yield, font=("Arial", 10, "bold"))
        self.lbl_yield.grid(row=1, column=3, sticky="w", padx=15, pady=5)

    def create_holdings_view(self):
        frame = ttk.LabelFrame(self.dashboard_frame, text="📊 현재 보유 종목 현황 (Live Holdings)", padding="10")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview
        columns = ('name', 'yield', 'pl', 'qty', 'price', 'time', 'step')
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', height=8)
        
        self.tree.heading('name', text='종목명')
        self.tree.heading('yield', text='수익률')
        self.tree.heading('pl', text='평가손익')
        self.tree.heading('qty', text='보유수량')
        self.tree.heading('price', text='현재가')
        self.tree.heading('time', text='보유시간')
        self.tree.heading('step', text='단계')
        
        self.tree.column('name', width=120, anchor="center")
        self.tree.column('yield', width=80, anchor="center")
        self.tree.column('pl', width=100, anchor="center")
        self.tree.column('qty', width=60, anchor="center")
        self.tree.column('price', width=80, anchor="center")
        self.tree.column('time', width=70, anchor="center")
        self.tree.column('step', width=60, anchor="center")
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill=tk.BOTH, expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Initial Load
        self.refresh_holdings()

    def refresh_holdings(self):
        status_path = 'status.json'
        if not os.path.exists(status_path):
            status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'status.json')
        
        # 1. Try reading status.json
        if not os.path.exists(status_path):
            return
            
        try:
            with open(status_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return
        
        # 2. Update Summary
        summary = data.get('summary', {})
        if summary:
            self.var_total_asset.set(f"{int(summary.get('total_asset', 0)):,} 원")
            self.var_total_buy.set(f"{int(summary.get('total_buy', 0)):,} 원")
            self.var_deposit.set(f"{int(summary.get('deposit', 0)):,} 원")
            
            pl = int(summary.get('total_pl', 0))
            yld = float(summary.get('total_yield', 0.0))
            
            self.var_total_pl.set(f"{pl:+,} 원")
            self.var_yield.set(f"{yld:+.2f} %")
            
            color = "red" if pl > 0 else "blue" if pl < 0 else "black"
            self.lbl_pl.config(foreground=color)
            self.lbl_yield.config(foreground=color)

        # 3. Update Holdings
        holdings = data.get('holdings', [])
        new_data_map = {h.get('stk_cd'): h for h in holdings if h.get('stk_cd')}
        
        existing_iids = set(self.tree.get_children())
        new_iids = set(new_data_map.keys())

        # Update or Insert
        for stk_cd, stock in new_data_map.items():
            name = stock.get('stk_nm', 'N/A')
            pl_rt = float(stock.get('pl_rt', 0))
            pl_amt = int(stock.get('pl_amt', 0))
            qty = int(stock.get('rmnd_qty', 0))
            price = int(stock.get('cur_prc', 0))
            step = stock.get('watering_step', '-')
            hold_time = stock.get('hold_time', '0분')
            
            values = (name, f"{pl_rt:+.2f}%", f"{pl_amt:,}", f"{qty:,}", f"{price:,}", hold_time, step)
            tag = 'profit' if pl_rt > 0 else 'loss' if pl_rt < 0 else ''

            if stk_cd in existing_iids:
                if self.tree.item(stk_cd, 'values') != values:
                    self.tree.item(stk_cd, values=values, tags=(tag,))
            else:
                self.tree.insert('', 'end', iid=stk_cd, values=values, tags=(tag,))

        # Delete old
        for iid in existing_iids:
            if iid not in new_iids:
                self.tree.delete(iid)

        self.tree.tag_configure('profit', foreground='red')
        self.tree.tag_configure('loss', foreground='blue')

    def auto_refresh_holdings(self):
        self.refresh_holdings()
        self.root.after(100, self.auto_refresh_holdings)

    def setup_logging(self):
        self.log_text.tag_config("INFO", foreground="white")
        self.log_text.tag_config("WARNING", foreground="yellow")
        self.log_text.tag_config("ERROR", foreground="red")
        
        handler = TextHandler(self.log_queue)
        self.log_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
        
        logger = logging.getLogger('trading_bot')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        self.poll_log_queue()

    def poll_log_queue(self):
        while True:
            try:
                record = self.log_queue.get_nowait()
            except queue.Empty:
                break
            
            try:
                msg = self.log_formatter.format(record)
                self.log_text.configure(state='normal')
                self.log_text.insert(tk.END, f"[{record.levelname}] ", record.levelname)
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
                self.log_text.configure(state='disabled')
            except Exception:
                pass
        
        self.root.after(100, self.poll_log_queue)

    def setup_sell_history(self):
        # Frame for buttons
        btn_frame = ttk.Frame(self.sell_history_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(btn_frame, text="🗑 매도내역 삭제 (Clear Log)", command=self.clear_sell_log).pack(side=tk.RIGHT)
        
        # Treeview
        frame = ttk.Frame(self.sell_history_frame)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('time', 'code', 'name', 'qty', 'pl_rt', 'reason')
        self.sell_tree = ttk.Treeview(frame, columns=columns, show='headings')
        
        self.sell_tree.heading('time', text='시간')
        self.sell_tree.heading('code', text='종목코드')
        self.sell_tree.heading('name', text='종목명')
        self.sell_tree.heading('qty', text='수량')
        self.sell_tree.heading('pl_rt', text='수익률')
        self.sell_tree.heading('reason', text='매도사유')
        
        self.sell_tree.column('time', width=140, anchor='center')
        self.sell_tree.column('code', width=80, anchor='center')
        self.sell_tree.column('name', width=100, anchor='center')
        self.sell_tree.column('qty', width=60, anchor='center')
        self.sell_tree.column('pl_rt', width=80, anchor='center')
        self.sell_tree.column('reason', width=120, anchor='center')
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.sell_tree.yview)
        self.sell_tree.configure(yscrollcommand=scrollbar.set)
        
        self.sell_tree.pack(side="left", fill=tk.BOTH, expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Styling
        self.sell_tree.tag_configure('profit', foreground='red')
        self.sell_tree.tag_configure('loss', foreground='blue')

        # Auto refresh
        self.auto_refresh_sell_history()

    def refresh_sell_history(self):
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sell_log.json')
        
        if not os.path.exists(log_path):
            # Clear if file deleted
            for item in self.sell_tree.get_children():
                self.sell_tree.delete(item)
            return
            
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except:
            return

        # Sort by time desc (recent first)
        logs.sort(key=lambda x: x.get('time', ''), reverse=True)
        
        existing_items = self.sell_tree.get_children()
        # If counts match and first item matches, assume no change (Optimization)
        if len(existing_items) == len(logs):
             if logs and len(existing_items) > 0:
                 first_val = self.sell_tree.item(existing_items[0])['values']
                 if first_val and str(first_val[0]) == str(logs[0].get('time')):
                     return

        for item in self.sell_tree.get_children():
            self.sell_tree.delete(item)
            
        for log in logs:
            pl_rt = float(log.get('profit_rate', 0))
            tag = 'profit' if pl_rt > 0 else 'loss'
            values = (
                log.get('time'),
                log.get('code'),
                log.get('name'),
                log.get('qty'),
                f"{pl_rt:+.2f}%",
                log.get('reason')
            )
            self.sell_tree.insert('', 'end', values=values, tags=(tag,))

    def auto_refresh_sell_history(self):
        self.refresh_sell_history()
        self.root.after(2000, self.auto_refresh_sell_history) # Refresh every 2s

    def clear_sell_log(self):
        if messagebox.askyesno("확인", "정말로 매도 내역을 모두 삭제하시겠습니까?"):
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sell_log.json')
            try:
                if os.path.exists(log_path):
                    os.remove(log_path)
                
                # Clear Treeview immediately
                for item in self.sell_tree.get_children():
                    self.sell_tree.delete(item)
                    
                messagebox.showinfo("알림", "삭제 완료되었습니다.")
            except Exception as e:
                messagebox.showerror("오류", f"삭제 실패: {e}")

    def start_bot(self):
        if self.bot_thread and self.bot_thread.is_alive():
            return
            
        self.lbl_status.config(text="상태: 실행 중... (Running)", foreground="green")
        logging.getLogger('trading_bot').info("🚀 봇 시스템 시작 요청 (Auto-Start or Manual)")
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        # [재시작 버그 수정] Start 버튼 클릭 시 DB 설정 수정하여 auto_start=True 강제화
        try:
            from get_setting import set_setting, get_setting
            set_setting('auto_start', True)
            
            # 아까 롤백된 청산 시간도 복구
            if get_setting('liquidation_time') == "15:20":
                set_setting('liquidation_time', "15:29")
            
            logging.getLogger('trading_bot').info("✅ Start 버튼 클릭: auto_start=True 설정 강제 적용 완료 (DB)")
        except Exception as e:
            print(f"설정 강제 수정 실패: {e}")
            
        self.bot_thread = threading.Thread(target=self.run_bot_async, daemon=True)
        self.bot_thread.start()

    def run_bot_async(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.bot_app = bot.MainApp()
            self.loop.run_until_complete(self.bot_app.run())
        except Exception as e:
            logging.getLogger('trading_bot').error(f"Bot Crashed: {e}")
        finally:
            self.loop.close()
            self.root.after(0, self.on_bot_stop)

    def stop_bot(self):
        if self.bot_app:
            self.bot_app.keep_running = False
            logging.getLogger('trading_bot').info("Stopping bot... (Wait for loop to finish)")
            self.btn_stop.config(state=tk.DISABLED)

    def on_bot_stop(self):
        self.lbl_status.config(text="상태: 정지됨 (Stopped)", foreground="red")
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def on_close(self):
        # "X 말고 그전껄로" 요청 반영: 묻지 않고 바로 종료
        if self.bot_thread and self.bot_thread.is_alive():
            self.stop_bot()
            # 봇 스레드 종료 대기를 위해 잠시 기다릴 수도 있지만,
            # GUI 반응성을 위해 바로 파괴하고 백그라운드 정리는 맡김
        self.root.destroy()
        # 확실한 종료를 위해 강제 exit 호출 (선택 사항)
        import os
        os._exit(0)

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Kiwoom Auto Trading Bot 시작")
    print("=" * 50)
    
    try:
        bot_app = bot.MainApp()
        asyncio.run(bot_app.run())
    except KeyboardInterrupt:
        print("\n⏹ 사용자에 의해 종료됨")
    except Exception as e:
        print(f"❌ 봇 오류: {e}")

