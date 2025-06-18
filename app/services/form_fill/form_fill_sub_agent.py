import json
import re
import os
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from utlis.Extract_resume import extract_text_from_resume


class FormFillSubAgent:
    def __init__(self, navigator, llm_model, resume_path, user_profile):
        print("🚀 Initializing FormFillSubAgent...")
        self.navigator = navigator
        self.llm_model = llm_model
        self.resume_path = resume_path
        self.user_profile = user_profile 
        
        print(f"📄 Resume path: {resume_path}")
        # print(f"👤 User profile keys: {list(self.user_profile.keys())}")
        print(self.user_profile)
        print("✅ FormFillSubAgent initialized successfully")

    async def answer_and_fill(self, questions):
        """Main function: Generate answers and check field status"""
        print("\n" + "="*80)
        print("🎯 Starting form analysis process...")
        print("="*80)
        
        print("\n📖 Step 1: Extracting resume content...")
        try:
            resume_text = extract_text_from_resume(self.resume_path)
            print(f"✅ Resume extracted successfully ({len(resume_text)} characters)")
        except Exception as e:
            print(f"❌ Error reading resume: {e}")
            return False

        print("\n🤖 Step 2: Generating answers with LLM...")
        answers = await self._generate_answers(questions, resume_text)

        print(f"\n Real answers look like these : {answers} \n \n")
        
        print("\n🎉 Form analysis completed!")
        print("="*80)
        return answers, True

    async def _generate_answers(self, questions, resume_text):
        """Generate answers using LLM with enhanced options handling"""
        print("🤖 Asking LLM to generate answers...")
        
        system_prompt = SystemMessage(content="""
            ROLE: LinkedIn Form Answer Generator
            OBJECTIVE: Generate accurate answers for form questions using resume data. If resume does not contain relevant info, use the provided user profile as fallback.
            
            INSTRUCTIONS:
            - Match resume details to form questions accurately
            - Return JSON array with element_id, question, and value
            - Use appropriate data types and formats
            - Set value to null if no relevant information found

            SKIP RULES:
            - Skip email fields (e.g., label includes "email")
            - Skip phone **country code** fields (e.g., dropdowns for country dialing codes)
            - DO NOT skip fields asking for phone numbers or mobile numbers

            ANSWER GENERATION RULES:
            1. For INPUT/TEXTAREA fields:
            - Provide direct text answers based on resume
            - Use exact format requested (e.g., numbers, dates)
            - Always use integers for experience (whole numbers only, no decimals like 0.5)

            2. For SELECT/DROPDOWN fields with options:
            - You will receive an "options" array with available choices (each with 'value', 'text', 'display')
            - Select the option that BEST MATCHES the resume data
            - Return the 'value' field (not 'text' or 'display') for form submission
            - If no perfect match, choose the closest reasonable option
            - If no reasonable match exists, set value to null

            3. For CHECKBOX/RADIO fields with options:
            - Same rules as SELECT fields
            - Choose the single best matching option from the provided array

            4. Fallback Strategy:
                - If resume text does NOT provide enough info to answer a question:
                    → Look for a relevant field in the user_profile object.
                - For example, use "expected_ctc", "preferred_location", or "work_authorization" from user_profile if relevant.

            EXAMPLES:

            Input Question:
            {
            "question": "Years of Python experience",
            "element_type": "select",
            "options": [
                {"value": "0-1", "text": "0-1 years", "display": "0-1 years"},
                {"value": "2-3", "text": "2-3 years", "display": "2-3 years"},
                {"value": "4-5", "text": "4-5 years", "display": "4-5 years"},
                {"value": "6+", "text": "6+ years", "display": "6+ years"}
            ]
            }
            Resume shows 3 years Python experience
            Answer: "2-3" (the value field)

            Input Question:
            {
            "question": "Do you have leadership experience?",
            "element_type": "select", 
            "options": [
                {"value": "Yes", "text": "Yes", "display": "Yes"},
                {"value": "No", "text": "No", "display": "No"}
            ]
            }
            Resume shows team lead role
            Answer: "Yes" (the value field)

            INPUT/OUTPUT FORMAT:
                                      
            Each answer object in the JSON array must include:
                - "element_id" (from the question input)
                - "question" (copied from input)
                - "value" (the selected or generated answer)
                - "element_type" (copied from input — input, select, radio, checkbox, textarea, etc.)
                            
            Input will include questions with their options (if applicable).
            Output ONLY valid JSON array:
            [
                {
                    "element_id": "form-element-123",
                    "question": "Full Name",
                    "value": "John Doe",
                    "element_type": "input"
                },
                {
                    "element_id": "select-element-456",
                    "question": "Years of experience",
                    "value": "4-5 years",
                    "element_type": "select"
                }
            ]


            CRITICAL RULES:
            - Output ONLY valid JSON array, no extra text
            - For select/radio/checkbox: value must be EXACTLY one of the provided options
            - Always use integers for experience years (no decimals)
            - Match resume data as accurately as possible to available options
        """)

        # Enhanced questions preparation with better options handling
        questions_data = []
        for q in questions:
            element_type = q.get('element_type', 'input').lower()
            
            question_data = {
                "element_id": q.get('element_id'),
                "question": q.get('question'),
                "element_type": element_type,
                "selector": q.get('selector')
            }
            
            # Include options for elements that have them
            if element_type in ['select', 'radio', 'checkbox', 'multiplechoice'] and q.get('options'):
                question_data["options"] = q.get('options')
                question_data["has_options"] = True
            else:
                question_data["options"] = None
                question_data["has_options"] = False
                
            questions_data.append(question_data)

        human_prompt = HumanMessage(content=json.dumps({
            "resume_text": resume_text,
            "user_profile": self.user_profile,
            "form_questions": questions_data,
            "instructions": "For questions with 'has_options': true, you MUST select your answer from the provided options array. For questions with 'has_options': false, provide direct text answers."
        }, indent=2))

        try:
            response = await self.llm_model.ainvoke([system_prompt, human_prompt])
            print(f"📥 LLM response received ({len(response.content)} characters)")
            
            # Enhanced JSON extraction with better error handling
            answer_json = re.search(r'\[\s*{.*}\s*\]', response.content, re.DOTALL)
            if not answer_json:
                print("❌ No valid JSON found in LLM response")
                print("Raw response preview:", response.content[:500])
                return []

            answers = json.loads(answer_json.group(0))
            
            # Validate answers against available options
            validated_answers = self._validate_answers_against_options(answers, questions)
            
            print(f"✅ Successfully parsed and validated {len(validated_answers)} answers")
            return validated_answers
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            print("Attempting fallback parsing...")
            return self._fallback_answer_parsing(response.content, questions)
            
        except Exception as e:
            print(f"❌ Error generating answers: {e}")
            return []

    def _validate_answers_against_options(self, answers, questions):
        """Validate that answers with options use valid option values"""
        validated = []
        
        # Create lookup for questions with options
        question_lookup = {q.get('element_id'): q for q in questions}
        
        for answer in answers:
            if not isinstance(answer, dict):
                continue
                
            element_id = answer.get('element_id')
            value = answer.get('value')
            
            # Find corresponding question
            question = question_lookup.get(element_id)
            if not question:
                validated.append(answer)  # Keep answer if we can't find question
                continue
                
            # Check if question has options
            options = question.get('options')
            element_type = question.get('element_type', '').lower()
            
            if options and element_type in ['select', 'radio', 'checkbox', 'multiplechoice']:
                # Validate that value is in options
                if value not in options and value is not None:
                    print(f"⚠️ Invalid option '{value}' for question '{question.get('question')}'. Available options: {options}")
                    # Try to find closest match
                    closest_match = self._find_closest_option(value, options)
                    if closest_match:
                        print(f"🔄 Using closest match: '{closest_match}'")
                        answer['value'] = closest_match
                    else:
                        print(f"❌ No suitable option found, setting to null")
                        answer['value'] = None
            
            validated.append(answer)
        
        return validated

    def _find_closest_option(self, value, options):
        """Find the closest matching option using fuzzy string matching"""
        if not value or not options:
            return None
            
        value_lower = str(value).lower()
        
        # First try exact match (case insensitive)
        for option in options:
            if str(option).lower() == value_lower:
                return option
        
        # Then try partial matches
        for option in options:
            option_lower = str(option).lower()
            if value_lower in option_lower or option_lower in value_lower:
                return option
        
        # For Yes/No questions, try to infer
        if len(options) == 2:
            yes_words = ['yes', 'true', '1', 'have', 'can', 'do', 'will', 'am', 'is']
            no_words = ['no', 'false', '0', 'dont', 'cannot', 'wont', 'not']
            
            if any(word in value_lower for word in yes_words):
                return next((opt for opt in options if 'yes' in str(opt).lower()), None)
            elif any(word in value_lower for word in no_words):
                return next((opt for opt in options if 'no' in str(opt).lower()), None)
        
        return None

    def _fallback_answer_parsing(self, response_content, questions):
        """Fallback method to extract answers if JSON parsing fails"""
        try:
            answers = []
            lines = response_content.split('\n')
            
            current_answer = {}
            for line in lines:
                line = line.strip()
                
                # Look for patterns like "element_id": "value"
                if '"element_id"' in line and ':' in line:
                    element_id = re.search(r'"element_id":\s*"([^"]+)"', line)
                    if element_id:
                        current_answer['element_id'] = element_id.group(1)
                
                elif '"question"' in line and ':' in line:
                    question = re.search(r'"question":\s*"([^"]+)"', line)
                    if question:
                        current_answer['question'] = question.group(1)
                
                elif '"value"' in line and ':' in line:
                    value = re.search(r'"value":\s*"([^"]*)"', line)
                    if value:
                        current_answer['value'] = value.group(1)
                        
                    # If we have all required fields, add to answers
                    if all(key in current_answer for key in ['element_id', 'question']):
                        answers.append(current_answer.copy())
                        current_answer = {}
            
            if answers:
                print(f"✅ Fallback parsing extracted {len(answers)} answers")
                return self._validate_answers_against_options(answers, questions)
                
        except Exception as e:
            print(f"❌ Fallback parsing failed: {e}")
        
        return []
