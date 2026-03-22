from __future__ import annotations


class ConversationResponseBuilder:
    def paywall_payload(self, paywall, wow) -> dict:
        return {
            "show": paywall.show_paywall,
            "type": paywall.paywall_type,
            "reason": paywall.reason,
            "usage_percent": paywall.usage_percent,
            "trial_active": paywall.trial_active,
            "trial_ends_at": paywall.trial_ends_at.isoformat() if getattr(paywall.trial_ends_at, "isoformat", None) else None,
            "trial_recommended": getattr(paywall, "trial_recommended", False),
            "upsell_recommended": getattr(paywall, "upsell_recommended", False),
            "wow_score": getattr(paywall, "wow_score", wow.score),
        }

    def tutor_response(
        self,
        *,
        tutor_mode_service,
        brain_output: dict,
        recommendation,
        tutor_context,
        reply: str,
        tutor_depth: str,
        paywall,
        wow,
    ) -> dict:
        payload = tutor_mode_service.response_payload(
            brain_output,
            recommendation,
            tutor_context,
            reply,
            tutor_depth=tutor_depth,
        )
        if paywall:
            payload["paywall"] = self.paywall_payload(paywall, wow)
        payload["wow"] = wow.__dict__
        return payload

    def standard_response(
        self,
        *,
        reply: str,
        analysis: dict,
        brain_output: dict,
        recommendation,
        features,
        paywall,
        wow,
    ) -> dict:
        response = {
            "reply": reply,
            "analysis": analysis,
            "drills": brain_output["drills"],
            "correction_feedback": brain_output.get("correction_feedback", []),
            "thinking_explanation": brain_output.get("thinking_explanation"),
            "next_action": recommendation.action if recommendation else None,
            "next_action_reason": recommendation.reason if recommendation else None,
            "lesson_difficulty": recommendation.lesson_difficulty if recommendation else None,
            "content_type": recommendation.content_type if recommendation else None,
            "tutor_mode": False,
            "subscription_tier": features.tier,
            "wow": wow.__dict__,
        }
        if paywall:
            response["paywall"] = self.paywall_payload(paywall, wow)
        return response
