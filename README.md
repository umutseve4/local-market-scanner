# local-market-scanner

Bursa sağlık sektöründeki işletmelerin **kamuya açık** dijital ayak izini tarar,
her işletmeye bir *dijital olgunluk skoru* verir ve "web sitesi / sosyal medya
hizmetine ihtiyacı olan" işletmeleri önceliklendirilmiş bir liste hâlinde çıkarır.

Bu bir satış aracı değil, bir **veri aracıdır**: çıktı, elle doğrulanması
gereken bir aday listesidir.

---

## Problem tanımı

Küçük bir sağlık işletmesine (diş polikliniği, fizyoterapi merkezi, optik,
eczane) hizmet satmak isteyen biri, kimin gerçekten dijital varlığa ihtiyacı
olduğunu bilmez. Bu proje o soruyu ölçülebilir hâle getirir:

> Bursa'daki hangi sağlık tesislerinin web sitesi yok, sosyal medya bağlantısı
> yok, ama ulaşılabilir bir telefonu var?

## Nasıl çalışır

```
Overpass API (OpenStreetMap)
        │  build_query() → Overpass QL
        ▼
  parse_response() → Business[]
        │  digital_maturity_score()
        ▼
  qualified_leads()  →  CSV + SQLite
```

### Dijital olgunluk skoru (0–100)

| Sinyal          | Puan |
| --------------- | ---: |
| Web sitesi      |  +40 |
| Sosyal medya    |  +25 |
| Telefon         |  +15 |
| E-posta         |  +10 |
| Çalışma saatleri|  +10 |

**Düşük skor = zayıf dijital varlık = daha iyi aday.**

| Skor    | Öncelik |
| ------- | ------- |
| ≤ 25    | high    |
| 26–55   | medium  |
| > 55    | low     |

Ağırlıklar `src/lms/models.py` içinde tek bir yerde tanımlıdır; kara kutu
değildir, değiştirilebilir ve testlerle sabitlenmiştir.

---

## Kurulum

```bash
git clone https://github.com/umutseve4/local-market-scanner.git
cd local-market-scanner
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # .env asla commit edilmez
```

## Kullanım

```bash
# 1) Bursa sağlık tesislerini tara (varsayılan bbox = Bursa ili)
PYTHONPATH=src python -m lms.cli scan --out data/bursa_health.csv --sqlite

# 2) Ağa çıkmadan, kayıtlı örnek veriyle dene
PYTHONPATH=src python -m lms.cli scan \
    --fixture tests/fixtures/overpass_sample.json --out data/sample.csv

# 3) Aday listesini üret
PYTHONPATH=src python -m lms.cli leads \
    --csv data/bursa_health.csv --max-score 25 --out data/leads.csv
```

Farklı bir bölge için:

```bash
PYTHONPATH=src python -m lms.cli scan --bbox 40.15,28.90,40.28,29.20
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v   # bağımlılıksız
PYTHONPATH=src pytest -q                                  # requirements ile
```

Testler **ağa çıkmaz**; Overpass yanıtı `tests/fixtures/overpass_sample.json`
dosyasından okunur.

---

## Veri kaynağı ve lisans

* Veri: [OpenStreetMap](https://www.openstreetmap.org/copyright), Overpass API
  üzerinden. OSM verisi **ODbL** ile lisanslıdır; türetilmiş veriyi yayımlarsan
  atıf ve lisans yükümlülüğün vardır.
* Overpass genel sunucusu ortak bir kaynaktır: gereksiz tekrarlı sorgu atma,
  sonuçları yerelde sakla.
* Google Maps HTML'i **kazınmaz** — bu Google Hizmet Şartları'nı ihlal eder.
  Google verisi istiyorsan resmî Places API'yi kendi anahtarınla kullan
  (`GOOGLE_PLACES_API_KEY`, henüz uygulanmadı).

## Bilinen kısıtlar

Bunlar gerçek kısıtlardır, ileride kapatılacak "eksikler" değil:

1. **OSM kapsama boşluğu.** Bursa'daki her sağlık işletmesi OSM'de kayıtlı
   değildir. "Web sitesi yok" sonucu, "OSM'de web sitesi etiketi yok"
   demektir — işletmenin gerçekten sitesi olmadığını kanıtlamaz. Aday listesi
   aramadan önce elle doğrulanmalıdır.
2. **Instagram aktifliği ölçülmez.** "Son 60 gündür paylaşım yapmamış hesaplar"
   gibi bir filtre yoktur. Instagram'ın resmî API'si üçüncü taraf hesaplar için
   bu veriyi vermez; kazımak Hizmet Şartları ihlalidir. Bu adım **manuel** bir
   zenginleştirmedir.
3. **Skor bir hipotezdir.** Ağırlıklar sezgiseldir, dönüşüm verisiyle
   kalibre edilmemiştir. Gerçek yanıt oranı toplandıkça revize edilmelidir.
4. **Tekilleştirme basittir.** Aynı işletmenin iki farklı OSM kaydı varsa
   ikisi de listeye girer.

## Hukuki uyarı (KVKK / İYS)

* Sadece kamuya açık veri toplanır.
* Kişisel veri (isim, telefon) saklandığı anda **KVKK** yükümlülüğü doğar:
  amaç sınırlaması, saklama süresi, silme talebine yanıt.
* İzinsiz toplu ticari e-posta/SMS göndermek **İYS** mevzuatını ihlal eder.
  Bu araç iletişim göndermez, sadece liste üretir. İletişim kurmak
  kullanıcının sorumluluğundadır.
* `.env` ve üretilen `data/*.csv`, `data/*.sqlite3` dosyaları `.gitignore`
  içindedir ve depoya girmez.

## Proje yapısı

```
src/lms/
  config.py           # ayarlar, Bursa bbox, OSM etiket filtreleri
  models.py           # Business, skorlama, telefon/URL normalizasyonu
  scoring.py          # filtreleme ve sıralama
  storage.py          # CSV + SQLite
  cli.py              # scan / leads komutları
  sources/overpass.py # Overpass QL üretimi ve yanıt ayrıştırma
tests/                # 51 test, ağ erişimi yok
sql/schema.sql        # PostgreSQL şeması (SQLite'tan büyüdüğünde)
```

## Durum

| Aşama            | Durum                                          |
| ---------------- | ---------------------------------------------- |
| Planlandı        | ✅                                              |
| Uygulandı        | ✅                                              |
| Test edildi      | ✅ 51 birim/entegrasyon testi (offline fixture) |
| Doğrulandı       | ⬜ Gerçek Overpass yanıtı henüz doğrulanmadı    |
| Dağıtıldı        | ⬜ Yok (CLI aracı)                              |
| Üretime hazır    | ⬜ Hayır                                        |

## Lisans

MIT — bkz. [LICENSE](LICENSE). Veri OSM'den gelir ve ODbL'ye tabidir.
