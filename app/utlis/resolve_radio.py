from bs4 import BeautifulSoup

async def resolve_radio_input_id(self, element_id: str, value: str) -> str:
    """
    Resolve the actual radio input ID based on either:
    - A fieldset/group ID (from LLM)
    - A base input ID without suffix (e.g., -0, -1)
    - A slightly incorrect input ID
    """
    try:
        html = await self.page.content()
        soup = BeautifulSoup(html, "html.parser")
        value = value.strip().lower()

        print(f"[resolve_radio_input_id] Resolving for: {element_id} → {value}")

        # 🔹 Case 1: Input ID is correct and matches value
        input_elem = soup.find("input", {"id": element_id, "type": "radio"})
        if input_elem:
            input_val = input_elem.get("data-test-text-selectable-option__input", "").strip().lower() or input_elem.get("value", "").strip().lower()
            if input_val == value:
                print(f"[resolve_radio_input_id] ✅ Exact input ID match: {element_id}")
                return element_id

        # 🔹 Case 2: Fieldset ID (e.g. LLM gives radio-button-form-component-... or anything that wraps inputs)
        fieldset = soup.find("fieldset", {"id": element_id})
        if fieldset:
            print(f"[resolve_radio_input_id] 🔍 Treating as fieldset ID")
            radio_inputs = fieldset.find_all("input", {"type": "radio"})
            for radio in radio_inputs:
                input_val = radio.get("data-test-text-selectable-option__input", "").strip().lower() or radio.get("value", "").strip().lower()
                if input_val == value and radio.has_attr("id"):
                    print(f"[resolve_radio_input_id] ✅ Found input inside fieldset: {radio['id']}")
                    return radio["id"]

        # 🔹 Case 3: Base input ID without suffix (-0, -1, etc.)
        if not element_id.endswith(tuple(f"-{i}" for i in range(6))):
            for i in range(6):
                candidate_id = f"{element_id}-{i}"
                input_elem = soup.find("input", {"id": candidate_id, "type": "radio"})
                if input_elem:
                    input_val = input_elem.get("data-test-text-selectable-option__input", "").strip().lower() or input_elem.get("value", "").strip().lower()
                    if input_val == value:
                        print(f"[resolve_radio_input_id] ✅ Corrected with suffix: {candidate_id}")
                        return candidate_id

        # 🔹 Case 4: Try matching by name (from input name attr)
        input_elems = soup.find_all("input", {"type": "radio"})
        for input_elem in input_elems:
            input_id = input_elem.get("id", "")
            input_name = input_elem.get("name", "")
            input_val = input_elem.get("data-test-text-selectable-option__input", "").strip().lower() or input_elem.get("value", "").strip().lower()

            if value in input_val or input_val in value:
                if element_id in input_id or element_id in input_name:
                    print(f"[resolve_radio_input_id] ✅ Matched by name or partial ID: {input_id}")
                    return input_id

        print(f"[resolve_radio_input_id] ❌ Could not resolve, returning original ID: {element_id}")
        return element_id

    except Exception as e:
        print(f"[resolve_radio_input_id] ⚠️ Error: {e}")
        return element_id
