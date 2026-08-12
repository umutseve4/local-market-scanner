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
        │  fetch_raw(): 3 endpoint × 3 deneme, üstel backoff, Retry-After
        ▼
  parse_response() → Business[]
        │  digital_maturity_score()
        ▼
  qualified_leads()  →  CSV + SQLite
        │  render_brief()
        ▼
  data/outreach_brief.md  (saha görüşme brifingi)
```

### Dayanıklılık

Overpass genel sunucuları düzenli olarak 429/504 döner. `fetch_raw`:

1. Sırayla `OVERPASS_URL` + `OVERPASS_MIRRORS` (varsayılan 2 yedek) dener.
2. Her endpoint için `MAX_RETRIES` (varsayılan 3) deneme yapar.
3. Beklemeyi `BACKOFF_SECONDS × 2^n` ile artırır; sunucu `Retry-After`
   gönderirse **o değer önceliklidir**.
4. Hepsi başarısızsa `OverpassUnavailableError` fırlatır → çıkış kodu `3`.

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

# 4) Saha görüşme brifingi (Markdown) üret
PYTHONPATH=src python -m lms.cli brief \
    --csv data/bursa_health.csv --limit 25 --out data/outreach_brief.md

# 5) Ayarları ve Overpass erişilebilirliğini teşhis et
PYTHONPATH=src python -m lms.cli doctor
PYTHONPATH=src python -m lms.cli doctor --offline   # ağa hiç çıkmaz
```

`Makefile` aynı komutları kısayola bağlar: `make scan`, `make leads`,
`make brief`, `make doctor`, `make test`, `make lint`, `make coverage`.

### `brief` ne üretir

Her aday için tek ekranda: eksik dijital varlıklar, önerilen teklif ve
görüşmeyi açacak bir cümle. Amaç, listeyi telefonda kullanılabilir hâle
getirmektir. Fiyat aralıkları `src/lms/outreach.py` içinde tek yerdedir.

### Ortam değişkenleri

Tümü isteğe bağlıdır; tam liste ve açıklamalar `.env.example` içinde.

| Değişken             | Varsayılan                            | Ne işe yarar                         |
| -------------------- | ------------------------------------- | ------------------------------------ |
| `OVERPASS_URL`       | `https://overpass-api.de/api/interpreter` | Birincil endpoint                |
| `OVERPASS_MIRRORS`   | 2 yerleşik yedek                      | Virgülle ayrık ek endpoint'ler       |
| `REQUEST_TIMEOUT`    | `180`                                 | Saniye cinsinden istek zaman aşımı   |
| `MAX_RETRIES`        | `3`                                   | Endpoint başına deneme (≥ 1)         |
| `BACKOFF_SECONDS`    | `2.0`                                 | Üstel backoff tabanı                 |
| `REQUESTS_CA_BUNDLE` | boş                                   | Kurumsal TLS proxy için CA paketi     |
| `DB_PATH`            | `data/market.sqlite3`                 | SQLite dosya yolu                    |

Geçersiz bir değer (örn. `MAX_RETRIES=many`) sessizce yok sayılmaz;
`ConfigError` fırlatılır ve çıkış kodu `1` olur.

### Çıkış kodları

| Kod | Anlamı                                                |
| --: | ----------------------------------------------------- |
|   0 | Başarılı                                              |
|   1 | Beklenen hata (dosya yok, boş sonuç, hatalı ayar)     |
|   2 | Beklenmeyen hata (bug — issue açın)                   |
|   3 | Veri kaynağına ulaşılamadı (tüm Overpass endpoint'leri)|

Bu kodlar cron/CI içinde ayırt edici davranış için sabittir ve testlidir.

Farklı bir bölge için:

```bash
PYTHONPATH=src python -m lms.cli scan --bbox 40.15,28.90,40.28,29.20
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v   # bağımlılıksız
PYTHONPATH=src pytest -q                                  # requirements ile
make coverage                                             # %80 alt sınır
```

**127 test, tamamı offline.** Overpass yanıtı
`tests/fixtures/overpass_sample.json` dosyasından okunur; HTTP katmanı
`FakeSession`/`FakeResponse` ile taklit edilir. Kapsam:

| Test dosyası                 | Neyi sabitler                                   |
| ---------------------------- | ----------------------------------------------- |
| `test_models.py`             | Skor ağırlıkları, telefon/URL normalizasyonu     |
| `test_scoring.py`            | Aday filtresi ve sıralama                        |
| `test_overpass.py`           | Overpass QL üretimi, yanıt ayrıştırma            |
| `test_overpass_retry.py`     | Retry, mirror geçişi, backoff, `Retry-After`     |
| `test_storage.py`            | CSV yazımı, SQLite upsert (idempotent)           |
| `test_config_validation.py`  | Ayar doğrulaması, env parse, anahtar sızıntısı   |
| `test_outreach.py`           | Brifing çıktısı (deterministik tarih)            |
| `test_cli_commands.py`       | 4 alt komut uçtan uca + çıkış kodu eşlemesi      |

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
* Ayrıntılar: [SECURITY.md](SECURITY.md).
* `.env` ve üretilen `data/*.csv`, `data/*.sqlite3` dosyaları `.gitignore`
  içindedir ve depoya girmez.

## Proje yapısı

```
src/lms/
  config.py           # Settings, doğrulama, Bursa bbox, OSM etiket filtreleri
  errors.py           # tipli hata hiyerarşisi (ConfigError, OverpassUnavailable...)
  models.py           # Business, skorlama, telefon/URL normalizasyonu
  scoring.py          # filtreleme ve sıralama
  outreach.py         # Markdown saha brifingi üretimi
  storage.py          # CSV + SQLite
  cli.py              # scan / leads / brief / doctor komutları
  sources/overpass.py # Overpass QL, retry + mirror fallback, check_status
tests/                # 127 test, ağ erişimi yok
sql/schema.sql        # PostgreSQL şeması (SQLite'tan büyüdüğünde)
```

## Durum

Sadece **gerçekten doğrulanmış** olanlar işaretlidir:

| Aşama         | Durum                                                          |
| ------------- | -------------------------------------------------------------- |
| Planlandı     | ✅                                                              |
| Uygulandı     | ✅ 4 CLI komutu, retry + mirror fallback, brifing üretimi        |
| Test edildi   | ✅ 127 test, tamamı offline, hepsi yeşil                        |
| Doğrulandı    | 🟡 Kısmi — CLI zinciri (`doctor → scan → leads → brief`) uçtan   |
|               | uca çalıştırıldı; **gerçek Overpass ağ çağrısı doğrulanmadı**   |
| Dağıtıldı     | ⬜ Yok (yerel CLI aracı)                                        |
| Üretime hazır | ⬜ Hayır                                                        |

### Ağ katmanı neden "doğrulanmadı"?

Bu depo, dışa TLS erişimi olmayan bir ortamda geliştirildi; `overpass-api.de`
çağrıları `CERTIFICATE_VERIFY_FAILED` ile döndü. Bu yüzden retry/mirror
mantığı **birim testleriyle** (`test_overpass_retry.py`) doğrulanmıştır,
canlı bir sorguyla değil. Kendi makinende ilk adım:

```bash
PYTHONPATH=src python -m lms.cli doctor
```

Her endpoint için `OK` veya hata satırı basar. Tüm endpoint'ler düşükse
çıkış kodu `3`'tür. Kurumsal proxy arkasındaysan `REQUESTS_CA_BUNDLE`
ayarla — kodda TLS doğrulaması **asla** kapatılmaz.

## Katkı ve güvenlik

* Geliştirme akışı ve "tamamlanma tanımı": [CONTRIBUTING.md](CONTRIBUTING.md)
* Sır yönetimi, veri lisansı ve KVKK notları: [SECURITY.md](SECURITY.md)
* Sürüm geçmişi: [CHANGELOG.md](CHANGELOG.md)

## Lisans

MIT — bkz. [LICENSE](LICENSE). Veri OSM'den gelir ve ODbL'ye tabidir.
