import os

def patch_file(path, search_text, replace_text):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if search_text in content:
        new_content = content.replace(search_text, replace_text)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Patched: {path}")
    else:
        print(f"Search text not found in: {path}")

# Fix Tribunal
patch_file('logic/tribunal.py', 
           "return 0, 0.1, f\"VETO MACRO: {macro_status['reason']}\"", 
           "return 0, 0.1, f\"VETO MACRO: {macro_status.get('reason', 'Não especificado')}\"")

# Fix Strategist Agent
patch_file('logic/strategist_agent.py',
           "md = state['macro_data']\n        news_sent = md.get('news_sentiment', 0.0)",
           "md = state.get('macro_data')\n        if md is None: md = {}\n        news_sent = md.get('news_sentiment', 0.0)")

# Fix Scout Bot Macro Status & Oracle Safety
patch_file('scout_bot.py',
           "self.macro_status = {'is_extreme': self.agent.radar.is_risk_off_extreme(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0))[0]}",
           "is_ext, m_reason = self.agent.radar.is_risk_off_extreme(macro_data.get('dxy_change',0), macro_data.get('sp500_change',0))\n                self.macro_status = {'is_extreme': is_ext, 'reason': m_reason}")

patch_file('scout_bot.py',
           "miro_data = {\"sentiment\": s_sent, \"confidence\": s_conf}",
           "if self.oracle_state is None: self.oracle_state = {'sentiment': 'Neutral', 'confidence': 0.5}\n                miro_data = {\"sentiment\": self.oracle_state.get(\"sentiment\", \"Neutral\"), \"confidence\": self.oracle_state.get(\"confidence\", 0.5)}")

# Fix Master Bot Macro Status & Oracle Safety 
patch_file('multicore_master_bot.py',
           "miro_data = {\"sentiment\": self.oracle_state[\"sentiment\"], \"confidence\": self.oracle_state[\"confidence\"]}",
           "if self.oracle_state is None: self.oracle_state = {'sentiment': 'Neutral', 'confidence': 0.5}\n                    miro_data = {\"sentiment\": self.oracle_state.get(\"sentiment\", \"Neutral\"), \"confidence\": self.oracle_state.get(\"confidence\", 0.5)}")

patch_file('multicore_master_bot.py',
           "macro_data, self.btc_dominance = await asyncio.wait_for(\n                        asyncio.gather(macro_task, btc_dom_task),\n                        timeout=20.0\n                    )",
           "macro_data, self.btc_dominance = await asyncio.wait_for(\n                        asyncio.gather(macro_task, btc_dom_task),\n                        timeout=20.0\n                    )\n                    if macro_data is None: macro_data = {'dxy_change': 0, 'sp500_change': 0, 'gold_change': 0}")

print("Hardening complete.")
