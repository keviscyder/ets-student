# E-testavimas planšetės programėlė

Įdiegimas pirmą kartą: planšetėje atidaryk
https://raw.githubusercontent.com/keviscyder/ets-student/main/app/E-testavimas.apk

Programėlė (nuo 1.3 versijos) paleidžiama patikrina `version.json`.
Jei `versionCode` didesnis už įdiegtą, ji parsisiunčia `apkUrl` ir pasiūlo įdiegti.

Naujai versijai išleisti: įkelk naują `E-testavimas.apk` ir padidink `versionCode`.

## Nuo 1.6 versijos: adresai iš version.json

Į `version.json` galima įrašyti:

    "startUrl": "https://naujas-adresas/...",
    "allowed": "https://etestavimas.streamlit.app/|https://naujas-adresas/"

`allowed` – leistini adresų pradžios, atskirti `|`, tik https ir su `/` po domeno.
`startUrl` turi prasidėti vienu iš leistinų adresų. Nauji adresai įsigalioja
kitą kartą paleidus programėlę. Jei laukų nėra, naudojamas Streamlit adresas.

Programėlės kodas ir pasirašymo raktas laikomi ne čia (archyvas ETS-planseciu-programele).
