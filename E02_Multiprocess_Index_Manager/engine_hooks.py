def fetch_from_db_and_build_index(version: int) -> dict:
    mock_db_records = [
        {"disease": "Malaria", "symptoms": ["fever", "chills", "headache"]},
        {"disease": "Dengue", "symptoms": ["fever", "joint pain", "rash"]},
        {"disease": "Common Cold", "symptoms": ["cough", "sneezing", "sore throat"]},
    ]
    if version >= 2:
        mock_db_records.append({"disease": "Typhoid", "symptoms": ["fever", "abdominal pain"]})

    inverted_index = {}
    for row in mock_db_records:
        for symptom in row["symptoms"]:
            inverted_index.setdefault(symptom, []).append(row["disease"])

    return {
        "version": f"v{version}",
        "source": "sqlite_mock_adapter",
        "terms": inverted_index
    }
