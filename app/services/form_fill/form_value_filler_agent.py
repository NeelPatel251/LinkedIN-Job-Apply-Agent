import asyncio
import json
from langchain_core.messages import HumanMessage, SystemMessage
from services.tools import create_tools
from services.form_fill.form_fill_agent import FormFillAgent
from services.form_fill.form_fill_sub_agent import FormFillSubAgent
from utlis.user_profile import load_user_profile
import os
from core.config import User_Profile_path

class FormValueFillerAgent:
    def __init__(self, navigator, llm_model, resume_path):
        self.navigator = navigator
        self.llm_model = llm_model
        self.resume_path = resume_path
        self.tools = create_tools(navigator, resume_path)
        self.model_with_tools = llm_model.bind_tools(self.tools)
        
    async def fill_form_values(self, answers):
        """
        Fill form values based on extracted answers
        Returns: success status and any remaining unfilled fields
        """
        print("\n🔄 Starting form value filling process...")

        # Load user profile
        user_profile_path = User_Profile_path
        if not os.path.exists(user_profile_path):
            print("❌ user_profile.json not found!")
            return False, []

        with open(user_profile_path, "r") as f:
            user_profile = json.load(f)

        resume_uploaded = user_profile.get("resume_uploaded", False)

        # Detect resume-related fields
        upload_related = lambda q: q and ("upload" in q.lower() or "resume" in q.lower())

        resume_fields = [f for f in answers if upload_related(f.get("question"))]

        # Manually handle resume upload if not already uploaded
        if resume_fields and not resume_uploaded:
            print("\n📄 Detected resume upload field(s).")
            print("Please upload your resume manually in the browser.")
            input("⏸️ Press Enter after you've uploaded the resume to continue...")

            # ✅ Mark resume as uploaded in user_profile
            user_profile["resume_uploaded"] = True
            with open(user_profile_path, "w") as f:
                json.dump(user_profile, f, indent=2)
            print("✅ Resume upload recorded in user_profile.json")

        # Remove all resume-related fields from processing
        filtered_answers = [f for f in answers if not upload_related(f.get("question"))]

        # Separate filled and unfilled fields
        fields_with_values = [f for f in filtered_answers if f.get("value") is not None]
        fields_without_values = [f for f in filtered_answers if f.get("value") is None]

        print(f"📝 Fields with values: {len(fields_with_values)}")
        print(f"❓ Fields without values: {len(fields_without_values)}")

        # Fill fields with values
        if fields_with_values:
            success = await self._fill_fields_with_values(fields_with_values)
            if not success:
                return False, fields_without_values

        # Handle any remaining unfilled fields
        if fields_without_values:
            print("\n⚠️ Some fields require manual input:")
            for field in fields_without_values:
                print(f"   - {field.get('question', 'Unknown question')}")
                print(f"     Element ID: {field.get('element_id', 'Unknown')}")

            print("\n🛑 AUTOMATION PAUSED")
            print("Please manually fill the remaining fields in the browser.")
            input("▶️ Press Enter to resume automation after manual input...")

        return True, []

    
    async def _fill_fields_with_values(self, fields_with_values):
        """Fill fields that have predetermined values"""
        print("\n🤖 LLM filling fields with predetermined values...")
        
        # Create system message for filling fields
        system_message = SystemMessage(content="""
            ROLE: Form Field Filler Agent

            OBJECTIVE:
            Fill form fields with the provided values using tools.

            STRATEGY:
            - Fill one field at a time
            - Handle different input types (text, checkbox, dropdown, etc.)
            - Be precise with element IDs

            CONSTRAINTS:
            - Use one tool call per response
            - Do NOT attempt to submit or navigate - only fill fields
            - If a field cannot be filled, skip it and continue
        """)
        
        for field in fields_with_values:
            element_id = field.get('element_id')
            question = field.get('question', 'Unknown')
            value = field.get('value')
            element_type = field.get('element_type', 'input').lower()
            
            print(f"   Filling: '{question}' with value: '{value}'")
            
            
            human_message = HumanMessage(content=f"""
                Fill the form field with the following details:
                - Element ID: {element_id}
                - Question: {question}
                - Value to fill: {value}
                - Element Type: {element_type}

                INSTRUCTIONS:
                - Use correct tool based on element_type.
                - For radio buttons, make sure to resolve the input ID before clicking.
                - For dropdowns (select), ensure value matches available option.
                - For input/textarea, insert the value directly.
            """)
            
            try:
                response = await self.model_with_tools.ainvoke([system_message, human_message])
                
                if response.tool_calls:
                    tool_call = response.tool_calls[0]
                    tool_name = tool_call['name']
                    # tool_args = tool_call['args']
                    tool_args = {
                        "element_id": tool_call['args'].get("element_id", field.get("element_id")),
                        "value": tool_call['args'].get("value", field.get("value")),
                        "element_type": tool_call['args'].get("element_type", field.get("element_type", "input").lower()),
                        "action": tool_call['args'].get("action", "fill")
                    }
                    
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    if tool:
                        try:
                            await tool.ainvoke(tool_args)
                            print(f"✅ Filled successfully")
                            await asyncio.sleep(1)  # Small delay between fills
                        except Exception as e:
                            print(f"❌ Failed to fill field: {e}")

                else:
                    print(f"❌ No tool call made for field")
                    
            except Exception as e:
                print(f"❌ Error filling field: {e}")
                
        return True
    
    async def handle_form_submission(self):
        """
        Handle form submission by pressing Next/Review/Submit buttons
        Returns: 'next', 'review', 'submit', or 'error'
        """
        print("\n🎯 Handling form submission...")
        elements_info = await self.navigator.get_page_elements()
        
        # Process button information to extract just the text content
        button_texts = []
        for button in elements_info.get('buttons', []):
            if isinstance(button, dict):
                # Extract text from button dict
                text = button.get('text', '') or button.get('content', '') or str(button)
            else:
                # If button is already a string
                text = str(button)
            
            if text and text.strip():
                button_texts.append(text.strip())
        
        # Create a clean list of available buttons for the AI
        available_buttons = "\n".join([f"- {text}" for text in button_texts if text])
        
        # print(f"\n Available Buttons : {available_buttons} \n")

        system_message = SystemMessage(content=f"""
        ROLE: Form Submission Handler
        OBJECTIVE:
        Handle form submission by clicking appropriate buttons in the correct order.
        
        BUTTONS:   
        1. "Submit Application" or "Submit" button - final submission
        3. "Review" button - if present, click it (review application)
        4. "Next" button - if present, click it (more questions/pages follow)
        
        STRATEGY:
        - Use a prioritized strategy:
            1. Click "Submit Application" or "Submit" if present (final submission)
            2. Otherwise, click "Review" if present (move to final review)
            3. Otherwise, click "Next" if present (more form steps)
        - Click only ONE button per call
        - Use click_element tool with the EXACT button text as identifier
        - Return the type of button clicked
        
        CRITICAL: 
        - Use the EXACT text content of the button as the identifier
        - DO NOT use numbers or indices as identifiers
        - Use element_type="button" and identifier=BUTTON_TEXT
        
        AVAILABLE BUTTONS:
        {available_buttons}
        
        EXAMPLE TOOL CALL:
        If you see a button with text "Next", use:
        click_element(element_type="button", identifier="Next", description="Clicking Next button to proceed")
        """)
        
        human_message = HumanMessage(content="""
            Based on the available buttons, click the correct one based on the following logic:

            1. If "Submit Application" or "Submit" button is present, click it — the application is complete and ready to submit.
            2. If "Review" button is present, click it — the form needs a final review before submission.
            3. If "Next" button is present, click it — there are more steps/questions to complete.

            Click only the FIRST button from this list that appears in the available buttons.
            You can use the exact text of the button as the identifier or you can match it with these buttons.
        """)

        
        try:
            response = await self.model_with_tools.ainvoke([system_message, human_message])
            
            if response.tool_calls:
                tool_call = response.tool_calls[0]
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                
                # Debug: Print what the AI is trying to click
                print(f"🔍 AI attempting to click: {tool_args}")
                
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if tool:
                    try:
                        result = await tool.ainvoke(tool_args)
                        response_text = str(result).strip().lower()
                        print(f"🔄 Click result: {response_text}")
                        
                        # Analyze the response to determine what button was clicked
                        if 'successfully clicked' in response_text:
                            if 'next' in response_text:
                                return 'next'
                            elif 'review' in response_text:
                                return 'review'
                            elif 'submit' in response_text:
                                return 'submit'
                            else:
                                return 'unknown'
                        else:
                            print(f"❌ Click failed: {response_text}")
                            return 'error'
                            
                    except Exception as e:
                        print(f"❌ Failed to click submission button: {e}")
                        return 'error'
                else:
                    print("❌ Tool not found for submission")
                    return 'error'
            else:
                print("❌ No tool call made for submission")
                return 'error'
                
        except Exception as e:
            print(f"❌ Error in form submission: {e}")
            return 'error'
    
    async def complete_form_process(self, initial_answers):
        """
        Complete the entire form filling and submission process
        Handles multiple pages/steps if Next buttons are present
        """
        print("\n🚀 Starting complete form process...")
        
        current_answers = initial_answers
        step_count = 1
        
        while True:
            print(f"\n📋 Processing form step {step_count}...")
            
            # Fill current form values
            success, remaining_fields = await self.fill_form_values(current_answers)
            
            if not success:
                print("❌ Form filling failed")
                return False
            
            # Wait a moment for fields to be processed
            await asyncio.sleep(2)
            
            # Handle form submission
            submission_result = await self.handle_form_submission()
            
            if submission_result == 'next':
                print("➡️ Next button clicked - extracting questions for next step...")
                
                print("\n \n")
                
                form_agent = FormFillAgent(self.navigator, self.llm_model)
                
                page_state = await form_agent.get_current_page_state()
                questions = await form_agent.extract_questions_only(page_state)

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
                    
                    result = "questions_extracted"

                if result == "questions_extracted":
                    questions = form_agent.last_extracted_questions
                    print(f"📝 Extracted {len(questions)} questions for next step")
                    
                    user_profile = load_user_profile()
                    form_filler = FormFillSubAgent(self.navigator, self.llm_model, self.resume_path, user_profile)
                    answers, analysis_result = await form_filler.answer_and_fill(questions)
                    
                    current_answers = answers
                    step_count += 1
                    
                    # Continue to next iteration of the loop
                    continue
                else:
                    print("❌ Failed to extract questions for next step")
                    return False
                    
            elif submission_result == 'review':
                print("👀 Review button clicked - proceeding to final submission...")
                await asyncio.sleep(2)
                
                # Try to submit after review
                final_submission = await self.handle_form_submission()
                
                if final_submission == 'submit':
                    print("✅ Application submitted successfully!")
                    return True
                else:
                    print("❌ Failed to submit after review")
                    return False
                    
            elif submission_result == 'submit':
                print("✅ Application submitted successfully!")
                return True
                
            else:
                print(f"❌ Form submission failed: {submission_result}")
                return False