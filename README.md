# SDTU Work Bot

> SamDAQU Boshqaruv Tizimi (Samarqand Davlat Arxitektura-Qurilish Universiteti yönetim sistemi) için Telegram bot — hesap bağlama ve görev bildirimlerini yönetir.

## Genel Bakış

Bu bot, telefon numarası kullanmadan kullanıcının Telegram hesabını web sistemindeki profiline bağlar. Kullanıcılar tek kullanımlık 6 haneli bir kod ile hesaplarını bağlar; sistem ardından kullanıcılara görev atama bildirimleri ve son tarih hatırlatmaları gönderebilir.

## Nasıl Çalışır

1. Kullanıcı bota `/start` yazar
2. Bot 6 haneli bir kod üretir, bunu kullanıcının `chat_id`'si ile birlikte `telegram_link_codes` tablosuna kaydeder (10 dakika geçerli)
3. Kullanıcı bu kodu web sistemindeki profil sayfasına girer
4. Backend kodu doğrular ve `chat_id`'yi kullanıcının `users` tablosundaki hesabına kaydeder
5. Sistem artık bu kullanıcıya Telegram üzerinden görev bildirimleri ve son tarih hatırlatmaları gönderebilir

```
Kullanıcı → /start → Bot kod üretir → Kullanıcı kodu web profiline girer
         → Backend chat_id'yi hesaba bağlar → Bildirimler aktif olur
```

## Özellikler

- Telefon numarası gerektirmeyen, tek kullanımlık kod ile bağlama akışı
- `/start` — bağlama kodu üretir
- `/durum` veya `/status` — sohbetin zaten bir hesaba bağlı olup olmadığını kontrol eder
- `send_task_notification()` — görev/son tarih mesajlarını sisteme dönüş linkiyle birlikte biçimlendirip gönderir
- Her `/start` çağrısında süresi dolmuş veya kullanılmamış eski kodların otomatik temizlenmesi
- Botu bloke eden kullanıcılar için zarif hata yönetimi — `telegram_chat_id` alanını otomatik temizler
- `ThreadedConnectionPool` ile PostgreSQL bağlantı havuzu
- `print()` yerine yapılandırılmış (structured) loglama

## Teknoloji Yığını

| Bileşen | Teknoloji |
|---|---|
| Dil | Python 3.12 |
| Bot framework | python-telegram-bot 21.6 |
| Veritabanı | PostgreSQL (psycopg2) |
| Deploy | Docker, GitHub → Portainer üzerinden |

## Proje Yapısı

```
.
├── bot.py              # Ana bot mantığı
├── requirements.txt    # Python bağımlılıkları
├── Dockerfile           # Container build tanımı
├── docker-compose.yml  # Compose servis tanımı
└── .env                # Lokal ortam değişkenleri (repoya eklenmez)
```

## Veritabanı Şeması

```sql
CREATE TABLE telegram_link_codes (
  code TEXT PRIMARY KEY,
  chat_id BIGINT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  used BOOLEAN DEFAULT false
);

ALTER TABLE users
  ADD COLUMN telegram_chat_id BIGINT UNIQUE;
```

## Ortam Değişkenleri

| Değişken | Açıklama | Örnek |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather)'dan alınan bot token'ı | `123456:ABC-DEF...` |
| `DATABASE_URL` | PostgreSQL bağlantı adresi | `postgresql://user:pass@host:5432/dbname` |
| `DB_POOL_MIN_CONNECTIONS` | Minimum havuz boyutu (opsiyonel, varsayılan `1`) | `1` |
| `DB_POOL_MAX_CONNECTIONS` | Maksimum havuz boyutu (opsiyonel, varsayılan `5`) | `5` |

Bu değerlerin gerçek halini hiçbir zaman commit etme. Lokal'de `.env` dosyasına yaz (zaten `.gitignore`'da); production'da Portainer'da ortam değişkeni olarak gir.

## Lokal Geliştirme

```bash
pip install -r requirements.txt
python bot.py
```

Proje köküne, yukarıdaki değişkenleri içeren bir `.env` dosyası eklediğinden emin ol.

## Deploy (GitHub → Portainer)

1. Değişiklikleri bu repoya push et
2. Portainer'da: **Stacks → [stack adı] → Pull and redeploy**
3. **Containers → [container] → Logs** kısmında botun hatasız başladığını doğrula:
   ```
   Bot çalışıyor...
   ```

Ortam değişkenleri repoda değil, doğrudan Portainer stack ayarlarında girilir.

### Kendi Sunucundaki PostgreSQL İçin Notlar

PostgreSQL aynı sunucuda ama Docker dışında çalışıyorsa, bot container'ının ona ağ erişimi olması gerekir:

- `postgresql.conf` içinde `listen_addresses` ayarını sadece `localhost` dışındaki bağlantıları da kabul edecek şekilde ayarla
- `pg_hba.conf` içine Docker bridge network aralığına izin veren bir satır ekle
- Bu dosyaları değiştirdikten sonra PostgreSQL'i yeniden başlat

## Lisans

Samarqand Davlat Arxitektura-Qurilish Universiteti için geliştirilen iç sistemdir. Tüm hakları saklıdır.
