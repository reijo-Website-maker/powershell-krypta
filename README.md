# PowerShell Krypta – Ubuntu Server -verkkopeli

Suomenkielinen PowerShellin perusteita opettava selainpeli. Ulkoasu on tumma hakkeriteema, jossa on neonvihreät korostukset.

## Ominaisuudet

- Käyttäjä voi rekisteröityä itse ja kirjautua sisään.
- Salasanat tallennetaan Werkzeugin salasanatiivisteinä, ei selväkielisinä.
- Jokaisella käyttäjällä on oma eteneminen, vihjeiden määrä ja pistemäärä.
- Seitsemän huonetta: cmdletit, komentojen haku, muuttujat, putket, kansiot, ehdot ja foreach.
- Vihje vähentää 10 pistettä; onnistunut tehtävä antaa 100 pistettä.
- SQLite tallentaa tiedot levylle.
- CSRF-tarkistus, istuntoevästeiden suojaus, parametrisoidut SQL-kyselyt ja perus-suojausotsakkeet.
- Pelaajan PowerShell-vastauksia ei koskaan suoriteta. Ne tarkistetaan vain tekstinä.

## Vaatimukset

Suositus: Ubuntu Server 24.04 LTS tai uudempi, Python 3.10+, sekä Nginx tuotantokäyttöön.

## A. Nopea testi lähiverkossa

1. Kopioi ZIP Ubuntu Serverille esimerkiksi SCP:llä tai pura se palvelimella.
2. Asenna paketit:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip
```

3. Pura projekti ja siirry kansioon. Esimerkiksi, jos ZIP on kotihakemistossa:

```bash
cd ~
unzip powershell-krypta-ubuntu.zip
cd powershell-krypta
```

4. Luo Python-virtuaaliympäristö ja asenna riippuvuudet:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Luo salainen istuntoavain ja käynnistä testipalvelin:

```bash
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export COOKIE_SECURE=0
python app.py
```

6. Selvitä palvelimen IP toisessa SSH-istunnossa tai palvelimella:

```bash
hostname -I
```

Avaa Windows-koneen selaimessa:

`http://UBUNTUN-IP:5000`

Esimerkiksi `http://192.168.1.50:5000`.

Jos UFW on käytössä ja testaat vain luotetussa lähiverkossa, voit sallia väliaikaisesti portin 5000:

```bash
sudo ufw allow 5000/tcp
```

Lopeta testipalvelin painamalla `Ctrl+C`. Flaskin sisäinen kehityspalvelin on testaukseen; julkiseen käyttöön käytä alla olevaa Gunicorn + Nginx -asennusta. Älä jätä porttia 5000 tarpeettomasti auki.

## B. Pysyvä palveluasennus Gunicornilla ja Nginxillä

Tämä asennus käyttää seuraavia polkuja:

- Sovellus: `/opt/powershell-krypta`
- Tietokanta: `/var/lib/powershell-krypta/krypta.db`
- Sisäinen Gunicorn: `127.0.0.1:8000`
- Nginx: portti 80 (HTTP); lisää HTTPS ennen internet-julkaisua.

### 1. Asenna Nginx ja luo palvelukäyttäjä

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
sudo useradd --system --user-group --home-dir /opt/powershell-krypta --shell /usr/sbin/nologin krypta
```

Jos `krypta`-käyttäjä on jo olemassa, älä suorita `useradd`-komentoa uudelleen.

### 2. Kopioi sovellus palvelinhakemistoon

Oletuksena olet purkanut projektin hakemistoon `~/powershell-krypta`:

```bash
sudo mkdir -p /opt/powershell-krypta
sudo cp -a ~/powershell-krypta/. /opt/powershell-krypta/
sudo chown -R root:krypta /opt/powershell-krypta
sudo chmod -R u=rwX,g=rX,o= /opt/powershell-krypta
```

### 3. Luo virtuaaliympäristö ja asenna paketit

```bash
sudo python3 -m venv /opt/powershell-krypta/.venv
sudo /opt/powershell-krypta/.venv/bin/pip install --upgrade pip
sudo /opt/powershell-krypta/.venv/bin/pip install -r /opt/powershell-krypta/requirements.txt
```

### 4. Luo salainen ympäristötiedosto

Komento luo satunnaisen salaisen avaimen. Älä jaa tätä avainta muille:

```bash
sudo bash -c 'umask 077; printf "SECRET_KEY=%s\nDATABASE_PATH=/var/lib/powershell-krypta/krypta.db\nCOOKIE_SECURE=0\n" "$(python3 -c "import secrets; print(secrets.token_hex(32))")" > /etc/powershell-krypta.env'
sudo chown root:krypta /etc/powershell-krypta.env
sudo chmod 640 /etc/powershell-krypta.env
```

`COOKIE_SECURE=0` sopii tässä vaiheessa vain paikalliseen HTTP-testaukseen. Kun HTTPS on otettu käyttöön, vaihda arvoksi `COOKIE_SECURE=1`.

### 5. Asenna systemd-palvelu

```bash
sudo cp /opt/powershell-krypta/deploy/powershell-krypta.service /etc/systemd/system/powershell-krypta.service
sudo systemctl daemon-reload
sudo systemctl enable --now powershell-krypta
sudo systemctl status powershell-krypta
```

Palvelun lokit:

```bash
sudo journalctl -u powershell-krypta -f
```

### 6. Ota Nginx käyttöön

```bash
sudo cp /opt/powershell-krypta/deploy/powershell-krypta.nginx /etc/nginx/sites-available/powershell-krypta
# Uudella, vain tätä peliä palvelevalla Nginx-palvelimella poista oletussivusto:
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/powershell-krypta /etc/nginx/sites-enabled/powershell-krypta
sudo nginx -t
sudo systemctl reload nginx
```

Nginx-asetus käyttää `default_server`-määritystä, jotta se toimii suoraan IP-osoitteella uudella palvelimella. Jos palvelimella on jo muita verkkosivustoja, älä poista niiden asetuksia: poista uuden asetuksen `default_server`-määre tai valitse oma verkkotunnus `server_name`-riville. Tarkista UFW:n tila:

```bash
sudo ufw status
```

Jos UFW on käytössä, salli Nginx:

```bash
sudo ufw allow 'Nginx HTTP'
```

Avaa selaimessa `http://UBUNTUN-IP`. Tuotantokäytössä älä avaa porttia 8000 internetiin: Gunicorn kuuntelee vain osoitteessa `127.0.0.1`.

## C. HTTPS internet-käyttöön

Älä julkaise kirjautumissivua internetiin HTTP-yhteydellä. HTTPS vaatii oman verkkotunnuksen, jonka DNS osoittaa palvelimen julkiseen IP-osoitteeseen, sekä palomuurin/reitittimen porttiohjaukset porteille 80 ja 443.

Kun verkkotunnus toimii ja Nginx on tavoitettavissa:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d oma-domain.fi
```

Vaihda sitten istuntoevästeen suojaus päälle:

```bash
sudo nano /etc/powershell-krypta.env
```

Muuta riviksi:

```ini
COOKIE_SECURE=1
```

Käynnistä sovellus uudelleen:

```bash
sudo systemctl restart powershell-krypta
```

Käytä oikeaa omaa verkkotunnustasi `oma-domain.fi`-esimerkin sijasta. Jos peli jää vain paikalliseen laboratorioverkkoon HTTP:n taakse, pidä `COOKIE_SECURE=0`; älä käytä tätä asetusta internet-julkaisussa.

## D. Hallintakomennot

```bash
sudo systemctl status powershell-krypta
sudo systemctl restart powershell-krypta
sudo systemctl stop powershell-krypta
sudo systemctl start powershell-krypta
sudo journalctl -u powershell-krypta -n 100 --no-pager
sudo nginx -t
```

Tietokanta on `/var/lib/powershell-krypta/krypta.db`. Ota siitä säännöllinen varmuuskopio esimerkiksi huoltoikkunan aikana:

```bash
sudo systemctl stop powershell-krypta
sudo cp /var/lib/powershell-krypta/krypta.db /var/lib/powershell-krypta/krypta-backup-$(date +%F).db
sudo chown krypta:krypta /var/lib/powershell-krypta/krypta-backup-*.db
sudo systemctl start powershell-krypta
```

## Vianetsintä

- **502 Bad Gateway:** tarkista `sudo systemctl status powershell-krypta` ja `sudo journalctl -u powershell-krypta -n 80 --no-pager`.
- **Sivu ei aukea:** tarkista IP (`hostname -I`), Nginx (`sudo systemctl status nginx`) ja UFW (`sudo ufw status`).
- **SECRET_KEY puuttuu:** tarkista `/etc/powershell-krypta.env` ja systemd-palvelun `EnvironmentFile`.
- **Tietokantavirhe tai permission denied:** varmista, että systemd-palvelu käyttää `StateDirectory=powershell-krypta` ja tietokanta on polussa `/var/lib/powershell-krypta/krypta.db`.
- **Kirjautumiseväste ei tallennu HTTPS:n jälkeen:** varmista, että sivu avataan HTTPS:llä ja `COOKIE_SECURE=1` on käytössä vain HTTPS:n kanssa.

## Tietoturvahuomio

Tämä on valmis laboratorio-/pienryhmäpelin pohja, ei auditoitu julkinen palvelu. Ennen laajaa internet-julkaisua lisää ainakin kirjautumisen yritysrajoitus, rekisteröitymisen väärinkäytön torjunta, valvonta ja testattu varmuuskopiointi. Pidä Ubuntu, Python-paketit ja Nginx päivitettyinä.
