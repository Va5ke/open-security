# Logovanje

Bitan alat u svakom kompleksnom informacionom sistemu koji garantuje pregled istorije događaja. U slučaju nastanka greške ili samo radi redovnog praćenja toka, moguće je neosporivo utvrditi koji entitet je izvršio koji događaj, u bilo kom trenutku. Radi uspostavljanja pravilnog mehanizma logovanja, potrebno je pratiti određena pravila i analizirati često korišćene tehnologije.

## Osnovne stavke loga

Kako bi prikazivao sve potrebne informacije, konvencija nalaže da log za određeni događaj sadrži sledeće stavke:

1. Ime događaja – identifikuje događaj u sistemu  
2. Poruka – ljudskim jezikom koncizno i razumljivo napisana informacija o događaju koji je nastao  
3. Vreme nastanka – govori o tome kada se desio događaj koji log opisuje  
4. Akter – korisnik ili API koji je prouzrokovao događaj  
5. Meta – aplikacija, uređaj, sistem i sl. koji je pogođen događajem  
6. Izvor – lokacija aktera za vreme događaja; može biti predstavljena pomoću IP adrese, hostname-a, države, identifikacionog koda uređaja itd.  
7. Dodatni podaci – detalji koji mogu nositi mali značaj u određenim situacijama, npr. nivo ozbiljnosti događaja (da li je u pitanju informacija, upozorenje, greška)  

Kako bi se obezbedila neporecivost, logovi moraju sadržati informaciju koja neosporivo može doći nazad do korisnika aktera, istovremeno ne otkrivajući njegove lične podatke. Prikladni načini da se to realizuje su beleženjem imejla (primer: Adobe-ov mehanizam logovanja), korisničkog ID-ja u sistemu, ili IP adrese njegovog uređaja. Neophodno je izbegavati prikaz lozinki, access token-a, enkripcionih ključeva, podataka sa platne kartice.

Logovi nastali na serverskoj strani se dalje šalju spoljnom servisu za logovanje. Vreme nastanka događaja opisanog u logu se beleži kad i sve ostale informacije, pre slanja spoljnom servisu, radi izbegavanja scenarija gde je servis u prekidu i ne zabeleži log u istom trenutku kad je on nastao.

Radi postizanja integriteta, potrebno je obezbediti prava pristupa logovima malom skupu privilegovanih korisnika u sistemu. U RBAC sistemu ta prava tipično imaju administratori, beležnici ili šefovi obezbeđenja.

## Logrotate

Logrotate je primer mehanizma za rotiranje logova koji koristi Linuks. U sistemima gde se perzistencija logova ostvaruje skladištenjem u lokalni fajl sistem logrotate pomaže da se reši neizbežni problem pretrpavanja memorije na disku.

Logrotate algoritam radi iterativno: na početku svakog ciklusa proverava da li je vreme za rotaciju (vreme za rotaciju se podešava u sistemu; može biti dnevno, nedeljno, mesečno...). Ukoliko jeste, stari log fajl se menja na osnovu strategije specificirane u konfiguraciji: create ili copytruncate. ¬Create preimenuje stari fajl i kreira novi u koji će pisati dalje logove, sa imenom koje je stari fajl nosio. Copytruncate kopira stari fajl, i iz originala briše ceo sadržaj kako bi mogao da piše u njega, dok kopija ima ulogu arhiviranog fajla. Obe strategije rezultuju u čišćenju prostora za pisanje novih logova, čuvajući sve prethodno zabeležene događaje.

U zavisnosti od konfiguracije, oslobađanje prostora na disku logrotate može realizovati periodičnim kompresovanjem. Na svaku rotaciju, stari fajlovi se kompresuju u .gz format i jedino sveži log fajl ostaje nepromenjen. Takođe postoji opcija brisanja, gde se specificira koliko maksimalno fajlova sme da ostane na disku, dok se oni iz davne prošlosti odbacuju.

Logrotate otvara vrata potencijalnim ranjivostima koje se najčešće svode na maliciozno baratanje fajlovima neposredno pre rotacije. Na primer, napadač može koristiti itrigger koji zamenjuje log direktorijum simboličkim linkom ka script fajlu u direktorijumu za Bash completion. Ovaj fajl uzrokuje da logrotate nesvesno kreira izmenljiv fajl sa root privilegijama, omogućujući napadaču direktan pristup za izvršavanje koda u srži sistema.

## ELK Stack

ELK Stack se sastoji od tri alata: Elasticsearch, Logstash i Kibana.

Logstash je prvi učesnik u toku rada ELK Stack-a i njegova uloga je da sakupi podatke iz raznih izvora i pošalje ih na željenu destinaciju, u našem slučaju u Elasticsearch. Koristi se kao pipeline podataka u kom korisnik inicijalno podešava parametre po svojoj potrebi: ulaz, filteri i izlaz.  
Ulaz (output) diktira ime fajla koji se tretira kao izvor podataka. Primer:
```
input {
  file {
    path => "/var/log/app/*.log"
    start_position => "beginning"
  }
}
```  
Filteri (filter) određuju način obrade podataka: njihovo parsiranje, modifikaciju i strukturiranje. Primer:
```
filter {
   grok {
    match => { "message" => "%{COMBINEDAPACHELOG}" }
  }
  date {
    match => [ "timestamp" , "dd/MMM/yyyy:HH:mm:ss Z" ]
  }
}
```  
Izlaz (output) definiše fajl ili ime servisa kome se podaci predaju nakon obrade. Primer:
```
output {
  elasticsearch {
    hosts => ["http://localhost:9200"]
    index => "app-logs-%{+YYYY.MM.dd}"
  }
  stdout { codec => rubydebug }
}
```

Elasticsearch je distribuirani pretraživački i analitički engine koji čuva podatke u formi JSON dokumenata unutar indeksa. Omogućuje brzu pretragu nad velikim skupovima podataka po imenima polja.

Za rad sa logovima indeksi su najčešće formirani po danu ili nedelji nastanka loga, radi efikasne pretrage logova po vremenu. Elasticsearch ima podršku Log4j 2, alat koji dodatno pomaže generisanju logova i daje mogućnost konfiguracije tri bitna svojstva: direktorijum u koji se logovi skladište, ime klastera (prefiks koji će svaki log fajl dobiti) i imena čvora (jedinstveno ime za svaki čvor u klasteru). U okviru Elasticsearch-a se može podesiti i port na kom trči (podrazumevani je localhost:9200).

Kibana je veb-aplikacija koja omogućuje interaktivno istraživanje, filtriranje i vizualizaciju podataka iz Elasticsearch-a. U opciji Discover korisnici mogu pretraživati logove pomoću fleksibilnih upita, filtrirati ih po poljima koja se nalaze u logu. Kibana nudi interaktivne i intuitivne grafikone za navigaciju kroz velike skupove podataka, podršku za rad sa mapama za geografske podatke, predefinisane filtere i agregacije za statistički pregled po histogramima, personalizovanje dashboard-ova i mnoge druge pogodnosti UI-a.

Iz ugla bezbednosti, ELK Stack pruža autentikaciju kao zaštitu od neovlašćenih korisnika pomoću alata kao što su Active directory, LDAP ili Elasticsearch native realm. Podržani su i SSO sertifikati, Kerberos i SAML. Autorizacija je omogućena u vidu prava na rukovanje Elasticsearch klasterima i grupisanju, i vidljivosti vizuelizovanih podataka na Kibani. Modularna struktura ELK Stack-a ima ključni značaj za postizanje slojevite bezbednosti, za svaki od alata moguće je odrediti koji korisnik ima koji nivo pristupa: bilo da je uvid u klastere, CRUD nad indeksima, pristup osetljivim dokumentima ili vidljivost polja u logovima.
