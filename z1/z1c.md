# Višefaktorska autentifikacija

## Tipovi višefaktorske autentifikacije

**MFA faktori:**

- **Faktor znanja:** nešto što znate - lozinka ili PIN
- **Faktor posedovanja:** nešto što imate - hardverski token
- **Nasledni faktor:** biometrijski podaci 

**Česte vrste:**

- Kodovi poslati imejlom
- Tekstualni tokeni: jednokratna lozinka (OTP) u obliku PIN-a kao SMS
- Virtualni tokeni: aplikacije trećih strana (TPA) daju nasumično generisan i često menjan kod
- Verifikacija pomoću biometrije: prepoznavanje lica, otiska prsta, zenice, glasa...
- Hardverski tokeni: proizvodi kodove pomoću malog uređaja, fizičkog tokena (ključ ili kartica); spada u najsigurnije MFA tehnike; primena u preduzećima, bankarstvu

## Fokus na odabranim faktorima

Lozinka se bira kao bezbedni standardni faktor autentifikacije na koji su korisnici navikli. Predstavlja faktor znanja. Bitno je da se definiše siguran način čuvanja (zadatak pod a) same lozinke i korisničkog imena.

Posebne aplikacije svakih npr. 30s generišu jednokratni kod Time-based One-Time Password (TOTP) na osnovu tajnog deljenog ključa i vremena. TOTP spada u najsigurnije tehnike višefaktorske autentifikacije jer vremenski ograničava ispravnost koda, pa je vreme otkrivanja takođe ograničeno pri pokušaju neželjenog napada na sistem. Prednost predstavlja što može da se koristi bez Interneta i što zavisi od ograničeno malo spoljnih faktora ne oslanjajući se na mrežu (poput SMS kodova) ili hardver. Smatra se da daje brže rezultate od nekih alternativa.

## Implementacija

Lozinka se kreira pri registraciji poštujući potreban nivo pravila, hešira i takva čuva u nekoj bazi.

Na serverskoj strani se generiše nasumični ključ (dužine 80-160 bitova) koji se čuva na serverskoj strani i koji korisnik prenosi u obliku QR-koda ili stringa do odabrane aplikacije za višefaktorsku autentifikaciju. Pri verifikaciji, aplikacija generiše svakih 30 sekundi novi kod čiji deo (npr. poslednja 4-8 karaktera) korisnik unosi u željeni sistem kao string. Kod se kreira kao heširana kombinacija tajnog ključa i Unix vremena podeljenog vremenskim intervalom (obično 30s). Serverska strana generiše kod na isti način i upoređuje svoj rezultat sa onim koji je korisnik uneo. Obnavljanje TOTP koda je obavezno da se omogući u slučaju gubitka pristupa aplikaciji za autentifikaciju. U tom slučaju, može da se primeni neki od drugih tehnika za autentifikaciju, s tim da je najčešće rešenje preko imejla.

## Greške i bezbednosni propusti

Unos TOTP koda predstavlja ranjivost kad su u pitanju phishing napadi, ali je ta ranjivost ograničena vremenom jer kodovi relativno kratko imaju svrhu, posle čega postaju beskorisni.

Deljeni tajni ključ je problem jer se čuva na više mesta (klijentskoj i serverskoj strani i prenosi se između njih), pa korisnici sa lošim namerama mogu da ga otkriju na jednom od njih i da budu u stanju da generišu validne TOTP kodove.

Da bi verifikacija mogla da se obavi, vreme generisanja koda na klijentskoj i serverskoj strani mora da bude sinhronizovano. Obično se dopusti neko kašnjenje da bi se uračunalo vreme potrebno korisniku da unese kod ili neke nepravilnosti u mreži. Problem s tim je da se produžava vreme validnosti koda što može dovesti do zloupotrebe na gorenavedeni način. Takođe, pošto se stalno generišu novi kodovi i proces verifikacije može da ne uspe iz prvog pokušaja, pa se javlja ranjivost kad su u pitanju brute-force napadi. Međutim, to se rešava ograničavanjem broj neuspešnih pokušaja za određeni nalog u definisanom vremenskom periodu nakon čega se onemogući dalje pokušavanje neko vreme (npr. 5 pokušaja u 5 minuta). Ako se to zaključavanje ponavlja, vreme zaključavanja može da se produžava. Može da se uvede CAPTCHA provera ili da se onemogući pristup sa neke IP adrese ako se detektuje mogući napad.

Treba ponovo spomenuti da je problem obnavljanja tajnog ključa potencijalan problem jer ne može da se reši bez oslanjanja na neke od drugih tehnika.

## Integracija MFA u Kibani

Integracija MFA u Kibani može da se omogući na više načina. Možemo da koristimo NGINX koji će vršiti autentifikaciju i tek onda omogućiti pristup Kibani ili da koristimo neki drugi servis poput Keycloak-a da se bavi ovim pitanjem. Pored toga možemo da iskoristimo Node.js biblioteku Syntetics CLI (@elastic/synthetics) da generišemo TOTP pomoću mfa komponente.
