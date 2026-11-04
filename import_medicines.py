"""
Downloads a public Indian medicine catalogue CSV and imports the first 500
usable product records into medicare.db and medicines.csv.

Source dataset fields include product name, price, manufacturer, type,
pack size and composition. It does NOT provide verified side effects,
age-specific precautions or dosage instructions. Those fields are left
as explicit "not provided" notices rather than invented medical advice.
"""
import csv
import os
import sqlite3
import urllib.request

DB = "medicare.db"
OUTPUT_CSV = "medicines.csv"
SOURCE_URL = (
    "https://raw.githubusercontent.com/junioralive/"
    "Indian-Medicine-Dataset/main/DATA/indian_medicine_data.csv"
)
LIMIT = 500

def download_source():
    print("Downloading public Indian medicine catalogue...")
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "MediCareStudentProject/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8-sig", errors="replace")

def main():
    try:
        raw = download_source()
    except Exception as error:
        print("\nCould not download the dataset.")
        print("Check your internet connection and try again.")
        print("Reason:", error)
        print("\nThe source CSV can also be downloaded manually from:")
        print("https://github.com/junioralive/Indian-Medicine-Dataset")
        return

    reader = csv.DictReader(raw.splitlines())
    required = ["name", "short_composition1"]
    if not reader.fieldnames or not all(col in reader.fieldnames for col in required):
        print("The downloaded CSV format was not as expected. No data imported.")
        print("Columns found:", reader.fieldnames)
        return

    records = []
    seen = set()
    for row in reader:
        name = (row.get("name") or "").strip()
        composition1 = (row.get("short_composition1") or "").strip()
        composition2 = (row.get("short_composition2") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        composition = ", ".join(x for x in [composition1, composition2] if x)
        records.append({
            "medicine_name": name,
            "brand_names": name,
            "composition": composition or "Composition not listed in source record",
            "manufacturer": (row.get("manufacturer_name") or "").strip(),
            "price": (row.get("price(₹)") or "").strip(),
            "dosage_form": (row.get("pack_size_label") or "").strip(),
            "uses": "Not supplied by the catalogue source. Check an authoritative product leaflet.",
            "side_effects": "Not supplied by the catalogue source. Check an authoritative product leaflet.",
            "age_precautions": "Age-specific precautions are not supplied by this catalogue. Ask a doctor or pharmacist.",
            "dosage_info": "No dose is provided. Do not calculate a dose from age alone; follow the exact product leaflet or prescriber.",
            "warnings": "Catalogue entry only. Confirm product identity, strength, suitability and warnings with a qualified healthcare professional.",
            "source": "Indian Medicine Dataset (GitHub; catalogue metadata)",
            "verified_status": "CATALOGUE METADATA ONLY - CLINICAL DETAILS NOT VERIFIED"
        })
        if len(records) >= LIMIT:
            break

    if len(records) < LIMIT:
        print("Only", len(records), "usable records were found; expected 500.")
        print("No partial import performed. Check the source dataset.")
        return

    fieldnames = list(records[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            brand_names TEXT DEFAULT '',
            composition TEXT DEFAULT '',
            manufacturer TEXT DEFAULT '',
            price TEXT DEFAULT '',
            dosage_form TEXT DEFAULT '',
            uses TEXT DEFAULT '',
            side_effects TEXT DEFAULT '',
            age_precautions TEXT DEFAULT '',
            dosage_info TEXT DEFAULT '',
            warnings TEXT DEFAULT '',
            source TEXT DEFAULT '',
            verified_status TEXT DEFAULT ''
        )
    """)
    con.execute("DELETE FROM medicines")
    con.executemany("""
        INSERT INTO medicines (
            medicine_name, brand_names, composition, manufacturer, price,
            dosage_form, uses, side_effects, age_precautions, dosage_info,
            warnings, source, verified_status
        ) VALUES (
            :medicine_name, :brand_names, :composition, :manufacturer, :price,
            :dosage_form, :uses, :side_effects, :age_precautions, :dosage_info,
            :warnings, :source, :verified_status
        )
    """, records)
    con.commit()
    count = con.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    con.close()

    print("\nSUCCESS!")
    print("CSV created:", OUTPUT_CSV)
    print("SQLite database updated:", DB)
    print("Medicine records imported:", count)
    print("\nNote: this dataset provides catalogue details, not clinically verified")
    print("side effects or dosing. The website labels these fields accordingly.")

if __name__ == "__main__":
    main()
