import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from core.log import get_logger

logger = get_logger(__name__)

def generate_html_report(
    backtest_results: Optional[Dict[str, Any]] = None,
    artefacts: Optional[List[Any]] = None,
    trace_logs: Optional[List[Any]] = None
) -> str:
    """
    Generates a beautifully styled, premium single-page HTML report containing
    backtest statistics, trade logs, generated AI decision cards, and trace logs.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # 1. Base Styles & Layout Template
    html_start = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FinAgent Executive Investment Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0b0f19;
            --bg-secondary: #111827;
            --bg-card: #1f2937;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-orange: #f59e0b;
            --border-color: #374151;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            line-height: 1.6;
            padding: 2rem 1rem;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 2.5rem;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }}
        
        header::after {{
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 300px;
            height: 100%;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%);
            pointer-events: none;
        }}
        
        h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(to right, #60a5fa, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .meta-stamp {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 500;
        }}
        
        h2 {{
            font-size: 1.5rem;
            margin: 2.5rem 0 1.2rem;
            font-weight: 600;
            border-left: 4px solid var(--accent-blue);
            padding-left: 0.75rem;
            color: #f3f4f6;
        }}
        
        /* Grid Cards */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .metric-card {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            padding: 1.5rem;
            border-radius: 8px;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        
        .metric-card:hover {{
            transform: translateY(-2px);
            border-color: #4b5563;
        }}
        
        .metric-label {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 0.5rem;
            font-weight: 600;
        }}
        
        .metric-value {{
            font-size: 1.75rem;
            font-weight: 700;
            color: #ffffff;
        }}
        
        .value-green {{ color: var(--accent-green) !important; }}
        .value-red {{ color: var(--accent-red) !important; }}
        
        /* Table Styles */
        .table-container {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow-x: auto;
            margin-bottom: 2rem;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }}
        
        th, td {{
            padding: 1rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        th {{
            background-color: #1f2937;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }}
        
        .badge-buy {{ background-color: rgba(16, 185, 129, 0.15); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-sell {{ background-color: rgba(239, 68, 68, 0.15); color: var(--accent-red); border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-liquidate {{ background-color: rgba(245, 158, 11, 0.15); color: var(--accent-orange); border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-watch {{ background-color: rgba(59, 130, 246, 0.15); color: var(--accent-blue); border: 1px solid rgba(59, 130, 246, 0.3); }}
        .badge-hold {{ background-color: #374151; color: var(--text-muted); border: 1px solid #4b5563; }}
        
        /* Artefact Cards */
        .artefacts-timeline {{
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .artefact-card {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.75rem;
            position: relative;
        }}
        
        .artefact-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1rem;
            margin-bottom: 1rem;
        }}
        
        .artefact-title {{
            font-size: 1.15rem;
            font-weight: 600;
            color: #ffffff;
        }}
        
        .evidence-list {{
            margin: 1rem 0;
            padding-left: 1.25rem;
        }}
        
        .evidence-list li {{
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
            color: #d1d5db;
        }}
        
        .commentary-box {{
            background-color: rgba(59, 130, 246, 0.05);
            border-left: 3px solid var(--accent-blue);
            padding: 0.75rem 1rem;
            border-radius: 0 4px 4px 0;
            font-size: 0.85rem;
            margin-top: 1rem;
            color: #9ca3af;
        }}
        
        /* Trace Collapsible */
        .details-wrapper {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            margin-bottom: 1rem;
            overflow: hidden;
        }}
        
        summary {{
            padding: 1rem 1.25rem;
            font-weight: 600;
            cursor: pointer;
            outline: none;
            background-color: #1f2937;
            user-select: none;
            font-size: 0.95rem;
        }}
        
        summary:hover {{
            background-color: #374151;
        }}
        
        .trace-content {{
            padding: 1.25rem;
            font-family: monospace;
            font-size: 0.85rem;
            background-color: #0b0f19;
            color: #38bdf8;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>FinAgent Decision & Performance Report</h1>
            <div class="meta-stamp">Report Generated at: {now_str}</div>
        </header>
"""

    # 2. Add Backtesting Metrics Dashboard (if available)
    if backtest_results:
        ret_val = backtest_results.get("total_return_pct", 0.0)
        ret_class = "value-green" if ret_val >= 0 else "value-red"
        bh_val = backtest_results.get("buy_and_hold_return_pct", 0.0)
        bh_class = "value-green" if bh_val >= 0 else "value-red"
        
        html_start += f"""
        <h2>Historical Backtest Summary</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Initial capital</div>
                <div class="metric-value">Rs. {backtest_results.get('initial_capital', 0.0):,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Final Equity</div>
                <div class="metric-value">Rs. {backtest_results.get('final_value', 0.0):,.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total return</div>
                <div class="metric-value {ret_class}">{ret_val:+.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Buy & hold return</div>
                <div class="metric-value {bh_class}">{bh_val:+.2f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win rate</div>
                <div class="metric-value">{backtest_results.get('win_rate_pct', 0.0):.1f}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total trades</div>
                <div class="metric-value">{backtest_results.get('total_trades', 0)}</div>
            </div>
        </div>
        """
        
        # Add Trades Executed Table
        trades_list = backtest_results.get("trades", [])
        if trades_list:
            html_start += """
            <h2>Executed Trade Logs</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Type</th>
                            <th>Price</th>
                            <th>Shares</th>
                            <th>Cost/Revenue</th>
                            <th>Trade PnL</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            for i, t in enumerate(trades_list, 1):
                t_type = t.get("type", "UNKNOWN")
                badge_class = f"badge-{t_type.lower()}"
                
                # Format money details
                price = f"Rs. {t.get('price', 0.0):,.2f}"
                shares = f"{t.get('shares', 0.0):.2f}"
                cost_rev = f"Rs. {t.get('cost', t.get('revenue', 0.0)):,.2f}"
                
                pnl_val = t.get("pnl")
                if pnl_val is not None:
                    pnl_pct = t.get("pnl_pct", 0.0)
                    pnl_class = "value-green" if pnl_val >= 0 else "value-red"
                    pnl_str = f"<span class='{pnl_class}'>Rs. {pnl_val:+.2f} ({pnl_pct:+.2f}%)</span>"
                else:
                    pnl_str = "<span class='text-muted'>-</span>"
                    
                html_start += f"""
                        <tr>
                            <td>{i}</td>
                            <td><span class="badge {badge_class}">{t_type}</span></td>
                            <td>{price}</td>
                            <td>{shares}</td>
                            <td>{cost_rev}</td>
                            <td>{pnl_str}</td>
                            <td>{t.get('timestamp', 'N/A')}</td>
                        </tr>
                """
            html_start += """
                    </tbody>
                </table>
            </div>
            """

    # 3. Add Generated Trade Decisions (DecisionArtefacts)
    if artefacts:
        html_start += "<h2>AI Investment Decisions</h2>"
        html_start += "<div class=\"artefacts-timeline\">"
        
        for art in artefacts:
            # Check type of artefact (can be pydantic model or dict)
            if hasattr(art, "model_dump"):
                art_dict = art.model_dump()
            elif hasattr(art, "__dict__"):
                art_dict = art.__dict__
            else:
                art_dict = art
                
            asset = art_dict.get("asset", "UNKNOWN")
            action = art_dict.get("action")
            action_str = action.value if hasattr(action, "value") else str(action)
            badge_class = f"badge-{action_str.lower()}"
            
            confidence = art_dict.get("confidence_score", 0)
            level = art_dict.get("confidence_level")
            level_str = level.value if hasattr(level, "value") else str(level)
            
            bullets = art_dict.get("evidence_bullets", [])
            risks = art_dict.get("risk_flags", [])
            commentary = art_dict.get("llm_commentary", "")
            
            html_start += f"""
            <div class="artefact-card">
                <div class="artefact-header">
                    <div class="artefact-title">{asset} Investment Recommendation</div>
                    <div>
                        <span class="badge {badge_class}">{action_str}</span>
                        <span class="badge" style="background-color: #374151; color: #ffffff;">Confidence: {confidence}% ({level_str})</span>
                    </div>
                </div>
                
                <div style="font-weight: 600; font-size: 0.9rem; margin-top: 0.5rem;">Supporting Evidence:</div>
                <ul class="evidence-list">
            """
            for b in bullets:
                html_start += f"<li>{b}</li>"
            html_start += "</ul>"
            
            if risks:
                html_start += f"""
                <div style="font-weight: 600; font-size: 0.9rem; margin-top: 0.75rem; color: var(--accent-orange);">Risk Warning & Data Gaps:</div>
                <ul class="evidence-list" style="color: var(--accent-orange);">
                """
                for r in risks:
                    html_start += f"<li style='color: var(--accent-orange);'>{r}</li>"
                html_start += "</ul>"
                
            if commentary:
                html_start += f"""
                <div class="commentary-box">
                    <strong>Analyst Commentary:</strong> {commentary}
                </div>
                """
                
            html_start += "</div>"
        html_start += "</div>"

    # 4. Add Collapsible Agent Trace Logs (Observability)
    if trace_logs:
        html_start += """
        <h2>System Trace & Observability Logs</h2>
        <div class="details-wrapper">
            <details>
                <summary>Click to view system execution trace logs</summary>
                <div class="trace-content">"""
        
        # Serialize trace logs cleanly
        for log_entry in trace_logs:
            if hasattr(log_entry, "model_dump_json"):
                log_str = log_entry.model_dump_json(indent=2)
            else:
                log_str = json.dumps(log_entry, indent=2)
            html_start += log_str + "\n\n"
            
        html_start += """</div>
            </details>
        </div>
        """

    # 5. Close Layout
    html_start += """
    </div>
</body>
</html>
"""
    return html_start

def save_report(html_content: str, output_path: str) -> str:
    """Saves the generated HTML report content to the designated output path."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"[exporter] Saved report to {output_path}")
    return output_path
