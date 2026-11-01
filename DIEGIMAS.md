# Mokinių programėlė ES serveryje (Sliplane)

Programėlė paleidžiama iš šakos `es-serveris` su `Dockerfile`. Streamlit debesis naudoja šaką `main`,
todėl abi versijos gali veikti kartu, kol planšetės perjungiamos.

## Vienkartinis paruošimas (sliplane.io)
1. Užsiregistruoti sliplane.io (prisijungti su GitHub paskyra keviscyder).
2. Sukurti serverį: regionas **Germany** arba **Finland**, mažiausias dydis.
3. Sukurti paslaugą (Service): šaltinis – GitHub repozitorija `keviscyder/ets-student`, šaka `es-serveris`,
   Dockerfile – šakninis `Dockerfile`, viešas HTTP, prievadas `8501`.
4. Aplinkos kintamieji (Environment variables, pažymėti kaip slapti):
   - `SUPABASE_URL` – Supabase projekto adresas
   - `SUPABASE_KEY` – **service_role** raktas
5. Health check kelias: `/_stcore/health`.
6. Deploy. Gautas adresas (pvz. `...sliplane.app`) įrašomas į naują APK versiją.

## Atnaujinimai
Nauja versija diegiama tik į šaką `es-serveris` sujungus pakeitimus ir tik tada, kai niekas nerašo testo.
