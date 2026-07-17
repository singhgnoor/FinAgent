import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Any
from core.state import RawSignal, SignalType
from core.graph import run_once
from core.ingestion_manager import stream_from_csv
from core.log import get_logger

logger = get_logger(__name__)

class BacktestEngine:
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.reset()
        
    def reset(self):
        self.cash = self.initial_capital
        self.position = 0.0
        self.entry_price = 0.0
        self.trades = []
        self.portfolio_value_history = []
        self.artefacts = []
        self.trace_logs = []
        
    def run(self, file_path: str, asset: str, delay: float = 0.0) -> Dict[str, Any]:
        """
        Runs the historical CSV price stream through the LangGraph pipeline
        and simulates paper trading execution.
        """
        self.reset()
        logger.info(f"[backtester] Starting backtest on {file_path} for {asset}...")
        
        # Load the CSV stream as a list of raw signals
        signal_generator = list(stream_from_csv(file_path, asset))
        if not signal_generator:
            raise ValueError(f"No price signals found in CSV file: {file_path}")
            
        first_close = signal_generator[0].payload["close"]
        final_close = signal_generator[-1].payload["close"]
        
        print("\n" + "=" * 60)
        print(f"            RUNNING BACKTEST FOR {asset}            ")
        print("=" * 60)
        print(f"Total Candlesticks: {len(signal_generator)}")
        print(f"Initial Capital   : Rs. {self.initial_capital:,.2f}")
        print(f"Stock Start Price : Rs. {first_close:.2f}")
        print(f"Stock End Price   : Rs. {final_close:.2f}")
        print("-" * 60)
        
        for idx, raw_signal in enumerate(signal_generator):
            close_price = raw_signal.payload["close"]
            
            # Execute the LangGraph pipeline
            final_state = run_once(raw_signal)
            
            # Extract recommendation from the synthesized decision artifact
            decision = final_state.get("artefact")
            if decision:
                self.artefacts.append(decision)
                
            # Collect trace logs for observability report
            traces = final_state.get("trace_log", [])
            for t in traces:
                self.trace_logs.append(t)
                
            rec_action = decision.action.value if decision else "HOLD"
            
            # Simulated Broker Execution logic:
            
            # 1. BUY: If agent recommends BUY and we hold no shares
            if rec_action == "BUY" and self.position == 0:
                self.position = self.cash / close_price
                self.entry_price = close_price
                buy_cost = self.cash
                self.cash = 0.0
                
                trade_log = {
                    "type": "BUY",
                    "price": close_price,
                    "shares": self.position,
                    "cost": buy_cost,
                    "timestamp": raw_signal.received_at.isoformat()
                }
                self.trades.append(trade_log)
                print(f"  [Trade #{len(self.trades)}] BUY  {self.position:.2f} shares at Rs.{close_price:.2f} (Cost: Rs.{buy_cost:.2f})")
                
            # 2. SELL: If agent recommends SELL and we hold shares
            elif rec_action == "SELL" and self.position > 0:
                sell_revenue = self.position * close_price
                pnl = sell_revenue - (self.position * self.entry_price)
                pnl_pct = (pnl / (self.position * self.entry_price)) * 100
                self.cash = sell_revenue
                
                trade_log = {
                    "type": "SELL",
                    "price": close_price,
                    "shares": self.position,
                    "revenue": sell_revenue,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "timestamp": raw_signal.received_at.isoformat()
                }
                self.trades.append(trade_log)
                print(f"  [Trade #{len(self.trades)}] SELL {self.position:.2f} shares at Rs.{close_price:.2f} (PnL: Rs.{pnl:+.2f} / {pnl_pct:+.2f}%)")
                
                # Reset position
                self.position = 0.0
                self.entry_price = 0.0
                
            # Keep track of daily portfolio net worth (cash + stock value)
            current_value = self.cash if self.position == 0 else (self.position * close_price)
            self.portfolio_value_history.append(current_value)
            
            if delay > 0:
                time.sleep(delay)
                
        # Final Liquidation: If we still hold shares on the final day, force sell them to determine ending cash
        if self.position > 0:
            final_value = self.position * final_close
            pnl = final_value - (self.position * self.entry_price)
            pnl_pct = (pnl / (self.position * self.entry_price)) * 100
            self.cash = final_value
            
            trade_log = {
                "type": "LIQUIDATE",
                "price": final_close,
                "shares": self.position,
                "revenue": final_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.trades.append(trade_log)
            print(f"  [Trade #{len(self.trades)}] LIQUIDATE {self.position:.2f} shares at Rs.{final_close:.2f} (PnL: Rs.{pnl:+.2f} / {pnl_pct:+.2f}%)")
            self.position = 0.0
            
        # Calculate Final Performance Metrics
        total_return = ((self.cash - self.initial_capital) / self.initial_capital) * 100
        buy_and_hold_return = ((final_close - first_close) / first_close) * 100
        
        # Calculate Win Rate (percentage of trades that closed in profit)
        closed_trades = [t for t in self.trades if t["type"] in ["SELL", "LIQUIDATE"]]
        winning_trades = [t for t in closed_trades if t["pnl"] > 0]
        win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0.0
        
        results = {
            "initial_capital": self.initial_capital,
            "final_value": self.cash,
            "total_return_pct": total_return,
            "buy_and_hold_return_pct": buy_and_hold_return,
            "total_trades": len(self.trades),
            "win_rate_pct": win_rate,
            "trades": self.trades,
            "portfolio_history": self.portfolio_value_history
        }
        
        # Export Reports (HTML & JSON)
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports")
            os.makedirs(reports_dir, exist_ok=True)
            
            # 1. Export HTML Report
            from core.exporter import generate_html_report, save_report
            html_content = generate_html_report(results, self.artefacts, self.trace_logs)
            html_filename = f"backtest_{asset}_{timestamp}.html"
            html_path = os.path.join(reports_dir, html_filename)
            save_report(html_content, html_path)
            results["report_html_path"] = html_path
            
            # 2. Export JSON Report
            serializable_artefacts = []
            for art in self.artefacts:
                if hasattr(art, "model_dump"):
                    serializable_artefacts.append(art.model_dump())
                elif hasattr(art, "__dict__"):
                    serializable_artefacts.append(art.__dict__)
                else:
                    serializable_artefacts.append(art)
                    
            serializable_traces = []
            for tr in self.trace_logs:
                if hasattr(tr, "model_dump"):
                    serializable_traces.append(tr.model_dump())
                elif hasattr(tr, "__dict__"):
                    serializable_traces.append(tr.__dict__)
                else:
                    serializable_traces.append(tr)
                    
            json_report_data = {
                "metrics": {
                    "initial_capital": self.initial_capital,
                    "final_value": self.cash,
                    "total_return_pct": total_return,
                    "buy_and_hold_return_pct": buy_and_hold_return,
                    "total_trades": len(self.trades),
                    "win_rate_pct": win_rate
                },
                "trades": self.trades,
                "artefacts": serializable_artefacts,
                "trace_logs": serializable_traces
            }
            
            def datetime_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError("Type not serializable")
                
            json_filename = f"backtest_{asset}_{timestamp}.json"
            json_path = os.path.join(reports_dir, json_filename)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(json_report_data, f, indent=2, default=datetime_serializer)
            results["report_json_path"] = json_path
            
            print(f"\n[Exporter] HTML Report Saved to: data/reports/{html_filename}")
            print(f"[Exporter] JSON Data Saved to: data/reports/{json_filename}")
            
        except Exception as e:
            logger.exception(f"[backtester] Failed to export reports: {e}")
            print(f"[Warning] Failed to generate reports: {e}")
            
        return results
