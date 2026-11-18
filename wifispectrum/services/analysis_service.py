"""Channel assessment, recommendations and generated insights.

Everything is computed from observed scan data. Network counts are never
presented as airtime utilisation, and no measurement is fabricated.
"""

from __future__ import annotations

import math

from ..core import channels
from ..core.models import (
    AccessPoint,
    AdapterInfo,
    Band,
    ChannelAssessment,
    ChannelRecommendation,
    Insight,
    ScanSnapshot,
)
from ..core.constants import rssi_quality


class ChannelAnalysisService:
    def __init__(self, region: str = "WORLD"):
        self.region = region

    # -- core assessment ---------------------------------------------------
    def assess(self, snapshot: ScanSnapshot, band: Band) -> ChannelAssessment:
        aps = snapshot.by_band(band)
        counts: dict[int, int] = {}
        for ap in aps:
            counts[ap.channel] = counts.get(ap.channel, 0) + 1

        congestion = channels.congestion_pct(aps, band)
        rec_data = channels.recommend_channel(band, aps, self.region)
        quietest = rec_data["channel"] if rec_data else None
        # "Busiest" follows the same relative-overlap index shown in the chart
        # and table, so the badge, the profile and the recommendation agree.
        busiest = None
        if rec_data and rec_data["scored"]:
            busiest = max(rec_data["scored"], key=lambda item: (item[1], -item[0]))[0]

        overlapping = 0
        for i, ap_a in enumerate(aps):
            for ap_b in aps[i + 1 :]:
                if ap_a.channel == ap_b.channel:
                    continue
                if channels.overlap_mhz(ap_a.span, ap_b.span) > 0:
                    overlapping += 1

        recommendation = None
        if rec_data:
            recommendation = ChannelRecommendation(
                band=band,
                channel=rec_data["channel"],
                frequency_mhz=channels.channel_to_freq(band, rec_data["channel"]),
                reason=rec_data["reason"],
                networks=rec_data["networks"],
                confidence=rec_data["confidence"],
                score=rec_data["score"],
                alternatives=rec_data["alternatives"],
            )

        return ChannelAssessment(
            band=band,
            counts=counts,
            congestion_pct=congestion,
            busiest_channel=busiest,
            quietest_channel=quietest,
            recommendation=recommendation,
            observations=len(aps),
            overlapping_pairs=overlapping,
        )

    def recommendations(self, snapshot: ScanSnapshot, band: Band, limit: int = 3) -> list[ChannelRecommendation]:
        aps = snapshot.by_band(band)
        data = channels.recommend_channel(band, aps, self.region)
        if not data:
            return []
        out: list[ChannelRecommendation] = []
        scored = data["scored"][:limit]
        for index, (channel, score) in enumerate(scored):
            confidence = data["confidence"] if index == 0 else ("medium" if index == 1 else "low")
            reason = data["reason"] if index == 0 else self._alternative_reason(score, channel, aps, band)
            out.append(
                ChannelRecommendation(
                    band=band,
                    channel=channel,
                    frequency_mhz=channels.channel_to_freq(band, channel),
                    reason=reason,
                    networks=len(aps),
                    confidence=confidence,
                    score=score,
                    alternatives=data["alternatives"],
                )
            )
        return out

    @staticmethod
    def _alternative_reason(score: float, channel: int, aps: list[AccessPoint], band: Band) -> str:
        if score <= 0.05:
            return "Clear of observed networks."
        if score < 0.35:
            return "Moderate weighted overlap from nearby networks."
        return "Busier fallback option; heavier observed overlap."

    # -- insights ----------------------------------------------------------
    def insights(self, snapshot: ScanSnapshot, band: Band, adapter: AdapterInfo | None) -> list[Insight]:
        aps = snapshot.by_band(band)
        assessment = self.assess(snapshot, band)
        insights: list[Insight] = []

        if not aps:
            insights.append(
                Insight(
                    "info",
                    "No networks observed in this band",
                    f"No beacon or probe response was seen on {band.label} yet. "
                    "Confirm the adapter supports this band and rescan.",
                    f"{band.label} \u2022 0 networks",
                )
            )
            return insights

        rec = assessment.recommendation
        if rec:
            insights.append(
                Insight(
                    "good",
                    f"Optimal observed channel: {rec.channel}",
                    rec.reason,
                    f"Ch {rec.channel} \u2022 {rec.frequency_mhz} MHz \u2022 confidence {rec.confidence}",
                )
            )

        if assessment.busiest_channel is not None and len(aps) >= 3:
            count = assessment.counts[assessment.busiest_channel]
            if count >= 3:
                avg = sum(ap.rssi for ap in aps if ap.channel == assessment.busiest_channel) / count
                severity = "critical" if count >= 5 or avg > -55 else "warning"
                insights.append(
                    Insight(
                        severity,
                        f"Congested channel detected: {assessment.busiest_channel}",
                        f"{count} networks share channel {assessment.busiest_channel}. "
                        "Channel count is a density indicator, not measured airtime.",
                        f"Ch {assessment.busiest_channel} \u2022 {count} APs \u2022 avg {avg:.0f} dBm",
                    )
                )

        strongest = max(aps, key=lambda ap: ap.rssi)
        if strongest.rssi >= -50:
            insights.append(
                Insight(
                    "info",
                    "Strong signal detected",
                    f"{strongest.display_ssid} is the strongest observed network on {band.label}.",
                    f"{strongest.rssi} dBm \u2022 ch {strongest.channel} \u2022 {rssi_quality(strongest.rssi)}",
                )
            )

        if assessment.overlapping_pairs >= 4:
            insights.append(
                Insight(
                    "warning",
                    "Multiple overlapping networks",
                    f"{assessment.overlapping_pairs} observed network pairs overlap in frequency.",
                    f"{assessment.overlapping_pairs} overlapping pairs \u2022 {len(aps)} networks",
                )
            )

        weak = [ap for ap in aps if ap.rssi <= -80]
        if weak:
            insights.append(
                Insight(
                    "info",
                    "Weak signals present",
                    f"{len(weak)} network{'s' if len(weak) != 1 else ''} observed below -80 dBm, "
                    "likely at the edge of reception.",
                    f"{len(weak)} APs \u2264 -80 dBm",
                )
            )

        wide = [ap for ap in aps if ap.width_mhz >= 40]
        if band is Band.GHZ_24 and wide:
            insights.append(
                Insight(
                    "warning",
                    "Wide channels on 2.4 GHz",
                    f"{len(wide)} network{'s' if len(wide) != 1 else ''} using 40 MHz occupy most of the band.",
                    f"{len(wide)} \u00d7 40 MHz",
                )
            )

        if band is Band.GHZ_24 and assessment.congestion_pct >= 45:
            five = snapshot.by_band(Band.GHZ_5)
            six = snapshot.by_band(Band.GHZ_6)
            if adapter and adapter.supports(Band.GHZ_5):
                better = "5 GHz" if len(five) < len(aps) else "6 GHz"
                insights.append(
                    Insight(
                        "info",
                        f"Consider another frequency band: {better}",
                        f"2.4 GHz density is {assessment.congestion_pct:.0f}% of the band. "
                        f"{len(five)} networks observed on 5 GHz and {len(six)} on 6 GHz.",
                        f"2.4 GHz {len(aps)} APs vs 5 GHz {len(five)} APs",
                    )
                )

        if not any(i.severity in ("warning", "critical") for i in insights):
            insights.insert(
                1,
                Insight(
                    "good",
                    "Channel plan looks healthy",
                    "No channel shows critical observed overlap in this band.",
                    f"Congestion estimate {assessment.congestion_pct:.0f}%",
                ),
            )

        order = {"critical": 0, "warning": 1, "good": 2, "info": 3}
        insights.sort(key=lambda item: order.get(item.severity, 9))
        return insights[:6]

    # -- chart helpers -----------------------------------------------------
    @staticmethod
    def distribution(snapshot: ScanSnapshot, band: Band, region: str = "WORLD") -> list[tuple[int, int]]:
        counts = snapshot.counts_by_channel(band)
        supported = channels.band_channels(band, region)
        merged = set(supported) | set(counts)
        return [(ch, counts.get(ch, 0)) for ch in sorted(merged)]

    @staticmethod
    def signal_histogram(aps: list[AccessPoint]) -> list[tuple[str, int]]:
        buckets = [("> -50", 0), ("-50..-60", 0), ("-60..-70", 0), ("-70..-80", 0), ("< -80", 0)]
        out = dict(buckets)
        for ap in aps:
            if ap.rssi > -50:
                out["> -50"] += 1
            elif ap.rssi > -60:
                out["-50..-60"] += 1
            elif ap.rssi > -70:
                out["-60..-70"] += 1
            elif ap.rssi > -80:
                out["-70..-80"] += 1
            else:
                out["< -80"] += 1
        return list(out.items())

    @staticmethod
    def stability(history: list[tuple[float, int]]) -> float:
        """0-100 stability score from RSSI standard deviation."""
        if len(history) < 3:
            return 0.0
        values = [rssi for _, rssi in history]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        deviation = math.sqrt(variance)
        return round(max(0.0, min(100.0, 100.0 - deviation * 9.0)), 1)
