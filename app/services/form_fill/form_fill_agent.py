import asyncio
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from services.tools import create_tools
from core.config import RESUME_PATH

class FormFillAgent:

    def __init__(self, navigator, llm_model):
        self.navigator = navigator
        self.llm_model = llm_model

        # Only use click_element tool for now
        self.tools = create_tools(navigator, RESUME_PATH)
        self.model_with_tools = llm_model.bind_tools(self.tools)

        self.last_extracted_questions = []

    async def get_current_page_state(self):
        """Get elements and HTML for Easy Apply modal if loaded"""
        try:
            elements = await self.navigator.get_page_elements()
            form_html = await self.navigator.extract_easy_apply_modal_html()
            return {
                **elements,
                "form_html": form_html
            }
        except Exception as e:
            print(f"❌ Error extracting page state: {e}")
            return await self.navigator.get_page_elements()

    async def apply_to_job(self):
        """Full flow: Click Easy Apply -> Wait -> Extract Questions"""
        system_message = SystemMessage(content=f"""
        ROLE: LinkedIn Easy Apply Form Interaction Agent

        OBJECTIVE:
        Start the job application by clicking the 'Easy Apply' button on a LinkedIn job post.

        STRATEGY:
        1. Find a button with label like "Easy Apply"
        2. Click it using the click_element tool

        RULES:
        - Only use the click_element tool in this step
        - Ignore buttons like "Apply on company site", "Save", or "Share"
        - If form loads, proceed to extract questions from it in the next step
        """)

        # Load page elements
        page_state = await self.navigator.get_page_elements()

        # Create human message context with buttons
        human_message = HumanMessage(content=f"""
        CURRENT PAGE STATE:

        URL: {page_state.get('current_url')}
        TITLE: {page_state.get('page_title')}

        BUTTONS:
        {page_state.get('buttons', [])}
        """)

        try:
            response = await self.model_with_tools.ainvoke([system_message, human_message])

            # Ensure tool call
            if response.tool_calls:
                click_call = response.tool_calls[0]
                tool_name = click_call['name']
                tool_args = click_call['args']

                tool = next((t for t in self.tools if t.name == tool_name), None)
                if tool:
                    print(f"🖱️ Clicking Easy Apply with args: {tool_args}")
                    await tool.ainvoke(tool_args)
                    print("✅ Easy Apply clicked.")
                else:
                    print(f"❌ Tool {tool_name} not found")
                    return "tool_not_found"
            else:
                print("⚠️ LLM did not make a tool call to click Easy Apply")
                return "no_tool_call"

        except Exception as e:
            print(f"❌ Error during Easy Apply click: {e}")
            return "click_error"

        # Wait for modal to load
        await asyncio.sleep(2)

        # Extract updated form state
        page_state = await self.get_current_page_state()
        questions = await self.extract_questions_only(page_state)

        if questions:

            print("\n" + "="*60)
            print("📋 EXTRACTED QUESTIONS:")
            print("="*60)
            
            # Print the extracted questions first
            for i, q in enumerate(questions, 1):
                print(f"{i}. Question: {q.get('question', 'Unknown')}")
                print(f"   Element ID: {q.get('element_id', 'Unknown')}")
                print(f"   Type: {q.get('element_type', 'Unknown')}")
                if q.get('options'):
                    print(f"   Options: {q.get('options')}")
                print("-" * 40)
            
            print("="*60)
            
            return "questions_extracted"

        print("⚠️ No questions found in form after clicking Easy Apply.")
        return "no_questions"

    async def extract_questions_only(self, page_state):
        """Extract form questions from modal HTML with multiple fallback methods"""
        form_html = page_state.get("form_html", "")
        
        if not form_html:
            print("⚠️ No form HTML found")
            return []

        try:
            self.last_extracted_questions = await self.extract_questions_with_llm(form_html)
            return self.last_extracted_questions

        except Exception as e:
            print(f"❌ LLM method failed: {e}")
            return []

    async def extract_questions_with_llm(self, form_html):
        """Extract questions and their element references using LLM"""
        system_message = SystemMessage(content="""
    ROLE: LinkedIn Easy Apply Form Parser
    TASK: Extract form questions AND their corresponding element identifiers from LinkedIn Easy Apply HTML.

    INSTRUCTIONS:
    1. Find form elements: <input>, <select>, <textarea>
    2. For each element, extract:
    - The question text (from associated <label>, placeholder, or nearby text)
    - The element identifier (id, name, or CSS selector)
    - The element type (input, select, textarea, checkbox, radio)
    - For SELECT, CHECKBOX, and RADIO elements: Extract ALL available options

    3. IGNORE: Phone country code dropdowns, submit buttons, navigation buttons
    4. ONLY extract elements that require user input

    OUTPUT FORMAT: Return ONLY a valid JSON array of objects. Examples:

    For INPUT elements:
    {
    "question": "Mobile phone number",
    "element_id": "single-line-text-form-component-formElement-urn-li-jobs-123",
    "element_type": "input",
    "selector": "#single-line-text-form-component-formElement-urn-li-jobs-123",
    "options": null
    }

    For SELECT elements:
    {
    "question": "Do you have experience with Python?",
    "element_id": "text-entity-list-form-component-formElement-urn-li-jobs-123",
    "element_type": "select",
    "selector": "#text-entity-list-form-component-formElement-urn-li-jobs-123",
    "options": ["Select an option", "Yes", "No"]
    }

    For CHECKBOX/RADIO elements:
    {
    "question": "Preferred work location",
    "element_id": "checkbox-group-123",
    "element_type": "checkbox",
    "selector": "input[name='work-location']",
    "options": ["Remote", "Hybrid", "On-site"]
    }

    CRITICAL RULES:
    - Your response must be valid JSON format, nothing else
    - For select/checkbox/radio elements, ALWAYS include "options" array
    - For input/textarea elements, set "options" to null
    - Extract option values from <option>, checkbox labels, or radio labels
    - Skip default/placeholder options like "Select an option" unless they're meaningful
    """)
        
        human_message = HumanMessage(content=f"HTML to analyze:\n{form_html}")
        
        try:
            response = await self.llm_model.ainvoke([system_message, human_message])
            response_content = response.content.strip()
            
            # Try JSON extraction
            json_match = re.search(r'\[\s*{.*}\s*\]', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    form_elements = json.loads(json_str)
                    if isinstance(form_elements, list):
                        # Validate and clean the extracted elements
                        cleaned_elements = self._validate_and_clean_elements(form_elements)
                        print(f"✅ LLM extracted {len(cleaned_elements)} form elements")
                        return cleaned_elements
                except json.JSONDecodeError as e:
                    print(f"❌ JSON parsing error: {e}")
                    print(f"LLM raw response (truncated): {response_content[:300]}...")
            
            # Enhanced fallback with basic HTML parsing
            form_elements = self._fallback_html_parsing(form_html)
            if form_elements:
                print(f"✅ Fallback HTML parsing extracted {len(form_elements)} elements")
                return form_elements
                
        except Exception as e:
            print(f"❌ Unexpected error during LLM extraction: {e}")
            return []

    def _validate_and_clean_elements(self, elements):
        """Validate and clean extracted form elements"""
        cleaned = []
        for element in elements:
            if not isinstance(element, dict):
                continue
                
            # Required fields
            if not all(key in element for key in ['question', 'element_type']):
                continue
                
            # Clean up the element
            cleaned_element = {
                'question': element.get('question', '').strip(),
                'element_id': element.get('element_id', ''),
                'element_type': element.get('element_type', 'input').lower(),
                'selector': element.get('selector', ''),
                'options': element.get('options')
            }
            
            # Validate options for select/checkbox/radio elements
            if cleaned_element['element_type'] in ['select', 'checkbox', 'radio']:
                if cleaned_element['options'] is None:
                    cleaned_element['options'] = []
                elif not isinstance(cleaned_element['options'], list):
                    cleaned_element['options'] = []
            else:
                cleaned_element['options'] = None
                
            cleaned.append(cleaned_element)
        
        return cleaned

    def _fallback_html_parsing(self, form_html):
        """Fallback method to parse HTML directly for basic extraction"""
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(form_html, 'html.parser')
            elements = []
            
            # Find all form elements
            form_elements = soup.find_all(['input', 'select', 'textarea'])
            
            for i, element in enumerate(form_elements):
                # Skip unwanted elements
                if self._should_skip_element(element):
                    continue
                    
                element_data = self._extract_element_data(element, i)
                if element_data:
                    elements.append(element_data)
            
            return elements
            
        except Exception as e:
            print(f"❌ Fallback parsing error: {e}")
            return []

    def _should_skip_element(self, element):
        """Check if element should be skipped"""
        # Skip submit buttons, hidden inputs, etc.
        if element.name == 'input':
            input_type = element.get('type', '').lower()
            if input_type in ['submit', 'button', 'hidden', 'reset']:
                return True
        
        # Skip country code dropdowns
        element_id = element.get('id', '').lower()
        if 'country' in element_id and 'code' in element_id:
            return True
            
        return False

    def _extract_element_data(self, element, index):
        """Extract data from a single form element"""
        try:
            # Get question text
            question = self._get_question_text(element)
            if not question:
                return None
                
            # Get element details
            element_id = element.get('id', f'element-{index}')
            element_type = element.name.lower()
            
            if element.name == 'input':
                element_type = element.get('type', 'text').lower()
                
            selector = f"#{element_id}" if element_id else f"{element.name}[{index}]"
            
            # Extract options for select/checkbox/radio
            options = None
            if element.name == 'select':
                options = self._extract_select_options(element)
            elif element_type in ['checkbox', 'radio']:
                options = self._extract_checkbox_radio_options(element)
                
            return {
                'question': question,
                'element_id': element_id,
                'element_type': element_type,
                'selector': selector,
                'options': options
            }
            
        except Exception as e:
            print(f"❌ Error extracting element data: {e}")
            return None

    def _get_question_text(self, element):
        """Extract question text from element"""
        # Try to find associated label
        element_id = element.get('id')
        if element_id:
            # Look for label with 'for' attribute
            label = element.find_previous('label', {'for': element_id})
            if label:
                return label.get_text(strip=True)
        
        # Try placeholder
        placeholder = element.get('placeholder')
        if placeholder and len(placeholder.strip()) > 2:
            return placeholder.strip()
        
        # Try nearby text (look for text in previous siblings)
        for sibling in element.find_all_previous(['label', 'span', 'div', 'p']):
            text = sibling.get_text(strip=True)
            if text and len(text) > 3 and len(text) < 200:
                return text
            if len(list(sibling.find_all_previous())) > 10:  # Don't go too far back
                break
        
        return None

    def _extract_select_options(self, select_element):
        """Extract options from select element"""
        options = []
        for option in select_element.find_all('option'):
            value = option.get('value', '').strip()
            text = option.get_text(strip=True)
            
            # Use text if available, otherwise use value
            option_text = text if text else value
            
            # Skip empty or placeholder options
            if option_text and option_text.lower() not in ['select an option', 'choose', 'select']:
                options.append(option_text)
        
        return options

    def _extract_checkbox_radio_options(self, element):
        """Extract options for checkbox/radio groups"""
        # This is a simplified version - in practice, you'd need to find
        # all related checkboxes/radios with the same name
        name = element.get('name')
        if not name:
            return []
        
        # Find all elements with the same name
        parent = element.find_parent('form') or element.find_parent('div')
        if not parent:
            return []
        
        options = []
        related_elements = parent.find_all('input', {'name': name})
        
        for elem in related_elements:
            # Look for associated label
            label_text = self._get_question_text(elem)
            if label_text:
                options.append(label_text)
        
        return options if len(options) > 1 else []
