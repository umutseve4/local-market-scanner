# local-market-scanner

[![CI](https://github.com/umutseve4/local-market-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/umutseve4/local-market-scanner/actions/workflows/ci.yml)
[![scan](https://github.com/umutseve4/local-market-scanner/actions/workflows/scan.yml/badge.svg)](https://github.com/umutseve4/local-market-scanner/actions/workflows/scan.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Bursa sağlık sektöründeki işletmelerin **kamuya açık** dijital ayak izini tarar,
her işletmeye bir *dijital olgunluk skoru* verir ve "web sitesi / sosyal medya
hizmetine ihtiyacı olan" işletmeleri önceliklendirilmiş bir liste hâlinde çıkarır.

Bu bir satış aracı değil, bir **veri aracıdır**: çıktı, elle doğrulanması
gereken bir aday listesidir.

> **Canlı doğrulama (2026-08-16):** GitHub Actions üzerinde gerçek Overpass
> API'ye karşı uçtan uca koştu — **989 işletme tarandı, 785 nitelikli lead**
> üretildi (1m 15s). Koşu kayıtları:
> [Actions → scan](https://github.com/umutseve4/local-market-scanner/actions/workflows/scan.yml).

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

## Bulutta çalıştır (kurulumsuz)

Depoyu klonlamadan, tarayıcıdan tek tıkla tarama:

1. **Actions → scan → Run workflow** (bbox boş bırakılırsa Bursa varsayılanı).
2. Koşu bitince **Summary** sekmesinde ilk lead'ler görünür.
3. **Artifacts → scan-results** içinde `leads.csv`, `lms.db`, `brief.md` ve
   `contract_report.md` 30 gün saklanır.

Workflow tanımı: [`.github/workflows/scan.yml`](.github/workflows/scan.yml)
— `doctor` ön kontrolü → `scan --track` (SQLite'a koşu kaydı) → `validate`
(veri sözleşmesi) → `brief` → özet + artifact.

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

# 6) Taramayı geçmişe kaydet ve koşular arası farkı gör (v0.3.0)
PYTHONPATH=src python -m lms.cli scan --fixture tests/fixtures/overpass_sample.json \
    --out data/sample.csv --track --db-path data/market.sqlite3
PYTHONPATH=src python -m lms.cli runs --db-path data/market.sqlite3
PYTHONPATH=src python -m lms.cli runs --db-path data/market.sqlite3 --changes 1

# 7) Veri sözleşmesini doğrula (9 kural; FAIL → çıkış kodu 1)
PYTHONPATH=src python -m lms.cli validate --csv data/sample.csv --report data/report.json

# 8) Parquet'e aktar (Hive partition: scan_date=YYYY-MM-DD/) — pip install .[export]
PYTHONPATH=src python -m lms.cli export --csv data/sample.csv --out-dir data/parquet

# 9) PostgreSQL'e yükle (idempotent upsert) — pip install .[pg]
docker compose up -d          # yerel Postgres 16 + şema
PYTHONPATH=src python -m lms.cli load-pg --csv data/sample.csv \
    --dsn postgresql://lms:lms@localhost:5432/lms
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
| `LMS_PG_DSN`         | boş                                   | `load-pg` için PostgreSQL DSN'i      |

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

**179 test, tamamı offline.** Overpass yanıtı
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
| `test_history.py`            | Koşu kaydı, diff (new/changed/unchanged)         |
| `test_contract.py`           | 9 sözleşme kuralı + JSON/Markdown rapor          |
| `test_exports.py`            | Parquet partition düzeni, eksik pyarrow hatası   |
| `test_pg_loader.py`          | Upsert SQL'i, batch, eksik psycopg hatası        |
| `test_cli_v030.py`           | `runs/validate/export/load-pg` + `--version`     |

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
  errors.py           # tipli hata hiyerarşisi + MissingDependencyError
  models.py           # Business, skorlama, telefon/URL normalizasyonu
  scoring.py          # filtreleme ve sıralama
  outreach.py         # Markdown saha brifingi üretimi
  storage.py          # CSV + SQLite
  history.py          # scan --track: koşu kaydı + koşular arası diff
  contract.py         # 9 kurallı veri sözleşmesi + JSON/Markdown rapor
  exports.py          # Hive-partitioned Parquet export (pyarrow opsiyonel)
  pg_loader.py        # PostgreSQL bulk upsert (psycopg opsiyonel)
  cli.py              # 8 komut: scan/leads/brief/doctor/runs/validate/export/load-pg
  sources/overpass.py # Overpass QL, retry + mirror fallback, check_status
tests/                # 179 test, ağ erişimi yok
sql/schema.sql        # PostgreSQL şeması (businesses + scan_runs + business_history)
docs/ARCHITECTURE.md  # modül haritası, veri akışı, tasarım kararları
.github/workflows/    # ci.yml (test+lint+pg) ve scan.yml (bulut taraması)
docker-compose.yml    # tek komutla yerel Postgres 16 + şema
```

## Durum

Sadece **gerçekten doğrulanmış** olanlar işaretlidir:

| Aşama         | Durum                                                          |
| ------------- | -------------------------------------------------------------- |
| Planlandı     | ✅                                                              |
| Uygulandı     | ✅ 8 CLI komutu, retry + mirror, history, contract, Parquet, PG  |
| Test edildi   | ✅ 179 test, tamamı offline, hepsi yeşil                        |
| Doğrulandı    | ✅ Canlı Overpass taraması GitHub Actions'ta uçtan uca koştu     |
|               | (2026-08-16: 989 işletme, 785 lead, 1m 15s — `scan #2`)         |
| Dağıtıldı     | ✅ `workflow_dispatch` ile bulutta tek tıkla koşuyor; çıktılar   |
|               | artifact olarak 30 gün saklanıyor                               |
| Üretime hazır | 🟡 Kısmi — zamanlanmış (cron) koşu ve dönüşüm verisiyle skor    |
|               | kalibrasyonu yok; skor hâlâ hipotez                             |

## Katkı ve güvenlik

* Geliştirme akışı ve "tamamlanma tanımı": [CONTRIBUTING.md](CONTRIBUTING.md)
* Sır yönetimi, veri lisansı ve KVKK notları: [SECURITY.md](SECURITY.md)
* Sürüm geçmişi: [CHANGELOG.md](CHANGELOG.md)

## Lisans

MIT — bkz. [LICENSE](LICENSE). Veri OSM'den gelir ve ODbL'ye tabidir.
