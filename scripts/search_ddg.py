import time
import pandas as pd
from ddgs import DDGS

OUTPUT_FILE = "data/candidate_links.csv"

HANDWRITTEN_REPLACEMENT_QUERIES = [
    "медична довідка Україна заповнена від руки фото",
    "бланк медичної довідки заповнений від руки",
    "медична карта пацієнта заповнена від руки",
    "направлення на аналізи заповнене від руки",
    "інформована згода пацієнта заповнена від руки",
    "анкета пацієнта заповнена від руки",
]

QUERIES = {
    "contract": [
        '"договір купівлі продажу" filetype:pdf',
        '"договір поставки" "підпис" filetype:pdf',
        '"договір надання послуг" "сторони" filetype:pdf',
        '"договір оренди" "підпис" filetype:pdf',
        '"акт приймання передачі" filetype:pdf',
        '"додаткова угода" "підпис" filetype:pdf',
    ],

    "financial_environmental_report": [
        '"оголошення" "оцінки впливу на довкілля" filetype:pdf',
        '"звіт з оцінки впливу на довкілля" "громадське обговорення" filetype:pdf',
        '"екологічна інформація" "планована діяльність" filetype:pdf',
        '"фінансовий звіт" "Україна" filetype:pdf',
        '"річний фінансовий звіт" "Україна" filetype:pdf',
        '"довідка про доходи" filetype:pdf',
    ],

    "receipt": [
        '"квитанція про оплату" "сума" filetype:pdf',
        '"рахунок квитанція" "платник" filetype:pdf',
        '"фіскальний чек" "Україна" filetype:pdf',
        '"платіжне доручення" "платник" filetype:pdf',
        '"рахунок фактура" filetype:pdf',
    ],

    "certificate_of_analysis": [
        '"сертифікат аналізу" filetype:pdf',
        '"сертифікат якості" "партія" filetype:pdf',
        '"сертифікат відповідності" filetype:pdf',
        '"паспорт якості" filetype:pdf',
        '"протокол випробувань" "зразок" filetype:pdf',
        '"лабораторний протокол" "зразок" filetype:pdf',
    ],

    "hospital_claim": [
        '"відшкодування витрат" "лікування" filetype:pdf',
        '"страховий випадок" "медична допомога" filetype:pdf',
        '"заява" "медичні послуги" "пацієнт" filetype:pdf',
        '"рахунок за медичні послуги" filetype:pdf',
        '"акт наданих медичних послуг" filetype:pdf',
    ],

    "patient_form": [
        '"анкета пацієнта" filetype:pdf',
        '"форма пацієнта" "медичний заклад" filetype:pdf',
        '"інформована згода пацієнта" filetype:pdf',
        '"інформована добровільна згода" filetype:pdf',
        '"медична карта пацієнта" filetype:pdf',
        '"направлення пацієнта" filetype:pdf',
    ],

    "medical_doctor_note": [
        '"анамнез" filetype:pdf',
        '"курс лікування" filetype:pdf',
        '"історія хвороби" filetype:pdf',
        '"виписка пацієнта" filetype:pdf',
        '"медичний висновок" filetype:pdf',
        '"лікарський висновок" filetype:pdf',
        '"консультаційний висновок" "лікар" filetype:pdf',
        '"довідка лікаря" "підпис" filetype:pdf',
    ],

    "logistics_financial": [
        '"накладна на відпуск товару" filetype:pdf',
        '"видаткова накладна" filetype:pdf',
        '"товарна накладна" filetype:pdf',
        '"товарно транспортна накладна" filetype:pdf',
        '"акт виконаних робіт" filetype:pdf',
        '"рахунок на оплату" filetype:pdf',
    ],

    "handwritten": [
        *HANDWRITTEN_REPLACEMENT_QUERIES,
        '"заява" "від руки" filetype:pdf',
        '"пояснювальна записка" filetype:pdf',
        '"письмові пояснення" filetype:pdf',
        '"заява громадянина" filetype:pdf',
        '"службова записка" filetype:pdf',
        '"службова записка" "від руки" filetype:pdf',
        '"службовий допис" filetype:pdf',
        '"службовий допис" "від руки" filetype:pdf',
        '"розписка" filetype:pdf',
        '"розписка" "від руки" filetype:pdf',
        '"розписка" "зразок" filetype:pdf',
        '"боргова розписка" filetype:pdf',
        '"боргова розписка" "від руки" filetype:pdf',
        '"розписка про отримання коштів" filetype:pdf',
        '"розписка про отримання коштів" "від руки" filetype:pdf',
        '"рапорт" filetype:pdf',
        '"рапорт" "від руки" filetype:pdf',
        '"рапорт поліції" "від руки" filetype:pdf',
        '"рапорт поліцейського" "від руки" filetype:pdf',
        '"рапорт військового" "від руки" filetype:pdf',
        '"військовий рапорт" "від руки" filetype:pdf',
        '"акт" "від руки" filetype:pdf',
        '"протокол допиту" filetype:pdf',
        '"пояснення" "від руки" filetype:pdf',
    ],

    "editable_docs": [
        '"договір" filetype:docx',
        '"накладна" filetype:docx',
        '"акт виконаних робіт" filetype:docx',
        '"інформована згода" filetype:docx',
        '"анкета пацієнта" filetype:docx',
        '"сертифікат якості" filetype:docx',
        '"довідка про доходи" filetype:docx',
    ],
}

rows = []

with DDGS() as ddgs:
    for category, queries in QUERIES.items():
        for query in queries:
            print(f"\nSearching: {category} | {query}")

            try:
                results = ddgs.text(
                    query,
                    region="ua-uk",
                    safesearch="off",
                    max_results=20,
                )

                for item in results:
                    title = item.get("title", "")
                    link = item.get("href", "")
                    snippet = item.get("body", "")

                    if not link:
                        continue

                    if "pdf" not in link.lower():
                        continue

                    rows.append({
                        "category": category,
                        "query": query,
                        "title": title,
                        "link": link,
                        "snippet": snippet,
                    })

            except Exception as e:
                print(f"Error: {e}")

            time.sleep(2)

df = pd.DataFrame(rows)

if not df.empty:
    df = df.drop_duplicates(subset=["link"])

df.to_csv(OUTPUT_FILE, index=False)

print(f"\nSaved {len(df)} candidate links to {OUTPUT_FILE}")
