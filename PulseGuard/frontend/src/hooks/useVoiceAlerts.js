/**
 * useVoiceAlerts — Web Speech API hook.
 * Announces CRITICAL and ZONE_ALARM alerts vocally.
 * Silently no-ops on browsers that don't support SpeechSynthesis.
 */
import { useEffect, useRef } from "react";

const SEVERITY_VOICE = new Set(["CRITICAL", "ZONE_ALARM"]);
const VOICE_RATE     = 1.05;
const VOICE_PITCH    = 0.9;
const VOICE_VOLUME   = 0.85;

export default function useVoiceAlerts(alerts) {
  // Voice alerts disabled
  const lastAnnouncedId = useRef(new Set());
  // const synth           = typeof window !== "undefined" ? window.speechSynthesis : null;
  const synth           = null;

  useEffect(() => {
    if (!synth) return;

    for (const alert of alerts) {
      if (
        !lastAnnouncedId.current.has(alert.alert_id) &&
        SEVERITY_VOICE.has(alert.severity) &&
        !alert.acknowledged
      ) {
        lastAnnouncedId.current.add(alert.alert_id);

        const text = alert.is_zone_alarm
          ? `Zone alarm. ${alert.zone_summary || alert.message}`
          : `Critical alert. ${alert.sensor_id}. ${alert.message}`;

        const utterance       = new SpeechSynthesisUtterance(text);
        utterance.rate        = VOICE_RATE;
        utterance.pitch       = VOICE_PITCH;
        utterance.volume      = VOICE_VOLUME;
        // Prefer a system English voice if available
        const voices = synth.getVoices();
        const eng    = voices.find((v) => v.lang.startsWith("en-") && v.localService);
        if (eng) utterance.voice = eng;

        synth.speak(utterance);
      }
    }
  }, [alerts, synth]);
}
