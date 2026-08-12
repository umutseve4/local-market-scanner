"""Outreach brief generation.

The scanner is only half of the revenue loop. This module turns a ranked lead
list into a Markdown brief that can be read before a phone call: what is
missing, what to offer, and what to say first.

Nothing here contacts anybody. It only formats data that is already in the
lead records, so it stays inside KVKK/GDPR limits for publicly published
business contact details.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from .models import Business

# Human-readable Turkish labels for the OSM category values we keep.
CATEGORY_LABELS: dict[str, str] = {
    "clinic": "poliklinik",
    "doctors": "muayenehane",
    "dentist": "diş kliniği",
    "hospital": "hastane",
    "pharmacy": "eczane",
    "veterinary": "veteriner kliniği",
    "centre": "sağlık merkezi",
    "doctor": "muayenehane",
    "laboratory": "laboratuvar",
    "physiotherapist": "fizyoterapi merkezi",
    "psychotherapist": "psikoterapi merkezi",
    "optician": "optisyen",
    "medical_supply": "medikal ürün satıcısı",
    "hearing_aids": "işitme cihazı merkezi",
}


def category_label(category: str) -> str:
    """Return a Turkish label for an OSM category, falling back to the raw value."""
    return CATEGORY_LABELS.get(category, category)


def missing_assets(business: Business) -> list[str]:
    """List the digital assets this business does not have."""
    gaps: list[str] = []
    if not business.has_website:
        gaps.append("web sitesi")
    if not business.has_social:
        gaps.append("sosyal medya bağlantısı")
    if not business.email:
        gaps.append("e-posta adresi")
    if not business.opening_hours:
        gaps.append("çalışma saatleri bilgisi")
    return gaps


def recommended_offer(business: Business) -> str:
    """Pick the single offer that matches the biggest gap.

    One offer per lead. A menu of five services in a first call reduces the
    reply rate; a single concrete proposal does not.
    """
    if not business.has_website and not business.has_social:
        return "Tek sayfalık tanıtım sitesi + Google Haritalar kaydının düzenlenmesi"
    if not business.has_website:
        return "Tek sayfalık tanıtım sitesi (randevu formu dahil)"
    if not business.has_social:
        return "Instagram profil kurulumu ve ilk 12 gönderilik içerik planı"
    if not business.opening_hours:
        return "Google İşletme Profili tamamlama ve haritalarda görünürlük düzeltmesi"
    return "Mevcut dijital varlıkların denetimi ve dönüşüm odaklı iyileştirme"


def opening_line(business: Business) -> str:
    """First sentence of the call, tailored to the observed gap."""
    label = category_label(business.category)
    if not business.has_website:
        return (
            f"Merhaba, Bursa'daki {label} işletmelerini inceliyorum. "
            f"{business.name} için açık kaynaklarda bir web sitesi göremedim; "
            "hasta aramalarının büyük kısmı bugün haritalar ve arama motoru "
            "üzerinden geliyor. 3 dakikanızı alabilir miyim?"
        )
    return (
        f"Merhaba, {business.name} için çevrimiçi görünürlüğü inceledim. "
        "Eksik kalan birkaç nokta var, kısaca paylaşabilir miyim?"
    )


def contact_line(business: Business) -> str:
    """Return the best available contact channel as a display string."""
    parts = [p for p in (business.phone, business.email, business.website) if p]
    return " | ".join(parts) if parts else "iletişim bilgisi yok"


def render_lead(business: Business, index: int) -> str:
    """Render a single lead as a Markdown block."""
    gaps = missing_assets(business)
    lines = [
        f"### {index}. {business.name}",
        "",
        f"- **Kategori:** {category_label(business.category)}",
        f"- **İlçe/Şehir:** {business.district or 'bilinmiyor'}",
        f"- **Adres:** {business.address or 'bilinmiyor'}",
        f"- **İletişim:** {contact_line(business)}",
        f"- **Dijital olgunluk skoru:** {business.digital_maturity_score()}/100 "
        f"(öncelik: {business.lead_priority()})",
        f"- **Eksikler:** {', '.join(gaps) if gaps else 'belirgin eksik yok'}",
        f"- **Önerilen teklif:** {recommended_offer(business)}",
        f"- **Açılış cümlesi:** {opening_line(business)}",
        "",
    ]
    return "\n".join(lines)


def render_brief(
    businesses: Iterable[Business],
    limit: int = 25,
    today: date | None = None,
) -> str:
    """Render a full Markdown outreach brief for the given leads."""
    items = list(businesses)[:limit]
    stamp = (today or date.today()).isoformat()
    header = [
        "# Saha Görüşme Brifingi — Bursa Sağlık Sektörü",
        "",
        f"- Oluşturulma tarihi: {stamp}",
        f"- Brifingdeki lead sayısı: {len(items)}",
        "- Veri kaynağı: OpenStreetMap (ODbL). Yalnızca işletmelerin kendi",
        "  yayımladığı kamuya açık iletişim bilgileri kullanılır.",
        "",
        "> Bu belge bir satış kaydı değildir. Görüşme sonucunu ayrı bir CRM",
        "> tablosuna yazın; bu dosya her taramada yeniden üretilir.",
        "",
        "---",
        "",
    ]
    if not items:
        header.append("_Kriterlere uyan lead bulunamadı. Skor eşiğini yükseltin._")
        return "\n".join(header) + "\n"

    blocks = [render_lead(b, i) for i, b in enumerate(items, start=1)]
    return "\n".join(header) + "\n".join(blocks)
