import os
import re
import json
import requests
from config.ai import get_provider_config

class CommunityModerationService:
    @staticmethod
    def moderate_content(title: str, content: str) -> dict:
        """
        Inspects post/comment title and content via DeepSeek AI.
        Returns:
            {
                "status": "APPROVED" | "REWRITTEN" | "REJECTED",
                "clean_title": str,
                "clean_content": str,
                "reason": str
            }
        """
        deepseek_api_key, deepseek_model = get_provider_config('DEEPSEEK')

        if not deepseek_api_key:
            # Fallback if key is missing
            return {
                "status": "APPROVED",
                "clean_title": title,
                "clean_content": content,
                "reason": "AI moderation key not supplied, published normally."
            }

        system_prompt = """
You are a strict safety officer and AI Content Moderator for RyuClass Online Community Forum (a Pantip-style educational platform).
Your task is to inspect user posts/comments for any forms of violent content, harassment, toxic/rude language, hate speech, illegal activities, or explicit profanity.

RULES:
1. If the content is appropriate and constructive:
   Return JSON with status = "APPROVED", clean_title = original title, clean_content = original content, reason = "".
2. If the content contains mild profanity, rude expressions, or aggressive tone that CAN be softened into polite Thai:
   Return JSON with status = "REWRITTEN", clean_title = sanitized title, clean_content = sanitized constructive title and description in polite Thai, reason = "ปรับเปลี่ยนถ้อยคำที่ไม่เหมาะสมโดย AI ให้สุภาพและเป็นมิตร".
3. If the content contains severe violence, physical threats, severe harassment, illegal acts, or extreme hate speech that CANNOT be softened:
   Return JSON with status = "REJECTED", clean_title = "", clean_content = "", reason = "พบเนื้อหารุนแรงหรือหยาบคายร้ายแรง ไม่สามารถเผยแพร่ในชุมชนได้".

OUTPUT FORMAT: You MUST respond ONLY with valid JSON and NO markdown code block wrappers:
{"status": "APPROVED", "clean_title": "...", "clean_content": "...", "reason": "..."}
"""

        user_prompt = f"TITLE: {title}\nCONTENT: {content}"

        headers = {
            'Authorization': f"Bearer {deepseek_api_key}",
            'Content-Type': 'application/json'
        }

        payload = {
            'model': deepseek_model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.1,
            'max_tokens': 1000
        }

        try:
            response = requests.post("https://api.deepseek.com/chat/completions", json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                raw_text = res_data['choices'][0]['message']['content'].strip()
                # Clean any markdown code blocks
                cleaned_text = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', raw_text, flags=re.DOTALL).strip()
                result = json.loads(cleaned_text)
                return {
                    "status": result.get("status", "APPROVED"),
                    "clean_title": result.get("clean_title", title),
                    "clean_content": result.get("clean_content", content),
                    "reason": result.get("reason", "")
                }
            else:
                print(f"DeepSeek Moderation Error Status: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"DeepSeek Moderation Connection Exception: {e}")

        # Default fallback if API fails
        return {
            "status": "APPROVED",
            "clean_title": title,
            "clean_content": content,
            "reason": "Default approved due to AI service timeout."
        }
