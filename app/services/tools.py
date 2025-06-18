import asyncio
from langchain_core.tools import tool
from core.config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD, JOB_LOCATION, JOB_TITLE, PHONE_NUMNER, RESUME_PATH

def create_tools(self, resume_path):
    """Create tools that the LLM can call"""

    @tool
    async def form_fill_tool(element_id: str, value: str, element_type: str = "input", action: str = "fill") -> str:
        """
        Enhanced form filling tool that handles all types of form elements.

        Args:
            element_id: The ID attribute of the HTML element to target.
            value: The value to enter, select, or use for action.
            element_type: One of 'input', 'select', 'textarea', 'radio', 'checkbox'.
            action: Action to perform - 'fill', 'select', 'check', 'uncheck', 'click'

        Returns:
            A success or error message.
        """
        try:
            print(f"🔧 [FormFillTool] {action.upper()} {element_type} with ID: {element_id} → {value}")
            if not await self.check_page_state():
                return "Error: Page not ready"

            # Try multiple selector strategies
            selectors_to_try = [
                f"#{element_id}",
                f"[id='{element_id}']",
                f"[name='{element_id}']",
                f"[data-test-id='{element_id}']",
                f"[aria-describedby='{element_id}']"
            ]

            elem = None
            for selector in selectors_to_try:
                try:
                    elem = await self.page.query_selector(selector)
                    if elem and await elem.is_visible():
                        break
                except:
                    continue

            if not elem:
                return f"Error: Element with ID '{element_id}' not found or not visible"

            await elem.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)

            if element_type.lower() == "input" or element_type.lower() == "textarea":

                print("Text input tool called : \n")
                # Handle text inputs and textareas
                await elem.click()
                await asyncio.sleep(0.2)
                
                # Clear existing content first
                await elem.fill("")
                await asyncio.sleep(0.1)
                
                # Fill with new value
                await elem.fill(str(value))
                await asyncio.sleep(0.3)
                return f"✅ Filled {element_type} '{element_id}' with '{value}'"

            elif element_type.lower() == "select":

                print("Dropdown Tool selected : \n")
                # Handle dropdown/select elements
                try:
                    # Try selecting by value first
                    await self.page.select_option(f"#{element_id}", value=str(value))
                    return f"✅ Selected '{value}' in dropdown '{element_id}'"
                except:
                    try:
                        # Try selecting by text content
                        await self.page.select_option(f"#{element_id}", label=str(value))
                        return f"✅ Selected '{value}' in dropdown '{element_id}'"
                    except:
                        return f"Error: Could not select '{value}' in dropdown '{element_id}'"

            elif element_type.lower() == "radio":

                print("Radio Tool Called : \n")

                from utlis.resolve_radio import resolve_radio_input_id

                resolved_id = await resolve_radio_input_id(self, element_id, value)
                
                if not resolved_id:
                    print("Could not resolve radio ID \n")
                    return f"❌ Could not resolve radio ID for value: '{value}'"
                
                element_id = resolved_id
                print(f"\n🎯 Resolved Radio ID : {element_id}")

                # ✅ Click label associated with the input
                label_selector = f'label[for="{element_id}"]'
                print(f"🔍 Trying label selector: {label_selector}")

                try:
                    label_elem = await self.page.query_selector(label_selector)
                    if label_elem and await label_elem.is_visible():
                        await label_elem.click()
                        await asyncio.sleep(0.3)
                        return f"✅ Clicked label for radio button '{value}'"
                    else:
                        print("⚠️ Label not found or not visible. Falling back to input.")
                except Exception as e:
                    print(f"⚠️ Error locating label: {e}. Falling back to input.")

                # Fallback: Try direct input element (less reliable on LinkedIn)
                fallback_selectors = [
                    f"[id='{element_id}']",
                    f"[name='{element_id}']",
                    f"[data-test-id='{element_id}']",
                    f"[aria-describedby='{element_id}']"
                ]

                elem = None
                for selector in fallback_selectors:
                    try:
                        elem = await self.page.query_selector(selector)
                        if elem and await elem.is_visible():
                            await elem.click()
                            await asyncio.sleep(0.3)
                            return f"✅ Clicked input radio button '{value}' (fallback)"
                    except:
                        continue

                return f"❌ Failed to click radio for value: '{value}'"


            elif element_type.lower() == "checkbox":

                print("Checkbox tool called : \n")
                # Handle checkboxes
                is_checked = await elem.is_checked()
                
                if action.lower() == "check" or (action.lower() == "click" and str(value).lower() in ["true", "yes", "1", "on"]):
                    if not is_checked:
                        await elem.click()
                        await asyncio.sleep(0.3)
                        return f"✅ Checked checkbox '{element_id}'"
                    else:
                        return f"✅ Checkbox '{element_id}' was already checked"
                        
                elif action.lower() == "uncheck" or (action.lower() == "click" and str(value).lower() in ["false", "no", "0", "off"]):
                    if is_checked:
                        await elem.click()
                        await asyncio.sleep(0.3)
                        return f"✅ Unchecked checkbox '{element_id}'"
                    else:
                        return f"✅ Checkbox '{element_id}' was already unchecked"
                        
                elif action.lower() == "toggle":
                    await elem.click()
                    await asyncio.sleep(0.3)
                    new_state = "checked" if not is_checked else "unchecked"
                    return f"✅ Toggled checkbox '{element_id}' to {new_state}"

            else:
                # Fallback - try to fill or click based on element type
                tag_name = await elem.evaluate("el => el.tagName.toLowerCase()")
                input_type = await elem.get_attribute("type") or ""
                
                if tag_name in ["input", "textarea"]:
                    if input_type.lower() in ["radio", "checkbox"]:
                        await elem.click()
                        return f"✅ Clicked {input_type} '{element_id}'"
                    else:
                        await elem.fill(str(value))
                        return f"✅ Filled {tag_name} '{element_id}' with '{value}'"
                elif tag_name == "select":
                    await self.page.select_option(f"#{element_id}", value=str(value))
                    return f"✅ Selected '{value}' in select '{element_id}'"
                else:
                    await elem.click()
                    return f"✅ Clicked element '{element_id}'"

        except Exception as e:
            return f"Error in form_fill_tool: {str(e)}"
        
    @tool
    async def click_element(element_type: str, identifier: str, description: str = "", post_click_selector: str = "") -> str:
        """
        Click on a web element (button, link, etc.)

        Args:
            element_type: Type of element ('button', 'link')
            identifier: Text content or unique identifier of the element
            description: Optional description of why clicking this element
            post_click_selector: Optional CSS selector to wait for after clicking

        Returns:
            Success/failure message
        """
        try:
            if not await self.check_page_state():
                return "Error: Page not accessible"

            print(f"🔧 Tool: Clicking {element_type} - {identifier}")
            if description:
                print(f"   Reason: {description}")

            if element_type == "link":
                links = await self.page.query_selector_all('a')
                if identifier.isdigit():
                    index = int(identifier)
                    if index < len(links):
                        await links[index].click()
                        if post_click_selector:
                            try:
                                await self.page.wait_for_selector(post_click_selector, timeout=8000)
                            except:
                                print(f"⚠️ post_click_selector '{post_click_selector}' not found after click.")
                        await self.wait_for_page_stable()
                        return f"Successfully clicked link at index {index}"
                    return f"Error: No link found at index {index}"
                else:
                    for link in links:
                        text = await link.text_content()
                        href = await link.get_attribute('href')
                        if (text and identifier.lower() in text.lower()) or (href and identifier in href):
                            await link.click()
                            if post_click_selector:
                                try:
                                    await self.page.wait_for_selector(post_click_selector, timeout=8000)
                                except:
                                    print(f"⚠️ post_click_selector '{post_click_selector}' not found after click.")
                            await self.wait_for_page_stable()
                            return f"Successfully clicked link: {text or href}"

            elif element_type == "button":
                
                await self.page.mouse.wheel(0, 1000)
                await self.page.wait_for_timeout(500) 
                buttons = await self.page.query_selector_all('button')

                if identifier.isdigit():
                    index = int(identifier)
                    if index < len(buttons):
                        await buttons[index].click()
                        if post_click_selector:
                            try:
                                await self.page.wait_for_selector(post_click_selector, timeout=8000)
                            except:
                                print(f"⚠️ post_click_selector '{post_click_selector}' not found after click.")
                        await self.wait_for_page_stable()
                        return f"Successfully clicked button at index {index}"
                    return f"Error: No button found at index {index}"

                for button in buttons:
                    text = await button.text_content()
                    if text and text.strip().lower() == identifier.lower(): 
                        
                        await button.scroll_into_view_if_needed()
                        await button.click()
                        if post_click_selector:
                            try:
                                await self.page.wait_for_selector(post_click_selector, timeout=8000)
                            except:
                                print(f"⚠️ post_click_selector '{post_click_selector}' not found after click.")
                        await self.wait_for_page_stable()
                        return f"Successfully clicked button with line 84: {text}"

                for button in buttons:
                    text = await button.text_content()
                    aria = await button.get_attribute("aria-label") or ""
                    role = await button.get_attribute("role") or ""
                    btn_id = await button.get_attribute("id") or ""

                    if text and identifier.lower() in text.lower():
                        text_lower = text.lower()
                        if any(third_party in text_lower for third_party in ['apple', 'google', 'facebook', 'microsoft', 'sso', 'continue with']):
                            continue

                        # Easy Apply filter button in sidebar (role=radio)
                        if ("easy apply" in text_lower or "easy apply" in aria.lower() or "searchFilter_applyWithLinkedin" in btn_id) and role == "radio":
                            await button.click()
                            if post_click_selector:
                                try:
                                    await self.page.wait_for_selector(post_click_selector, timeout=8000)
                                except:
                                    print(f"⚠️ post_click_selector '{post_click_selector}' not found after click.")
                            await self.wait_for_page_stable()
                            self.add_to_history("click_element", f"button: {identifier}", "success")
                            return f"Successfully clicked Easy Apply filter button: {text or aria}"

                        # Job detail page Easy Apply button (text is nested in a span)
                        if "easy apply" == identifier.lower():
                            span = await button.query_selector("span.artdeco-button__text")
                            if span:
                                span_text = (await span.inner_text()).strip().lower()

                                if "easy apply" in span_text:
                                    await button.click()
                                    if post_click_selector:
                                        try:
                                            await self.page.wait_for_selector(post_click_selector, timeout=8000)
                                        except:
                                            print(f"⚠️ post_click_selector '{post_click_selector}' not found after click.")
                                    await self.wait_for_page_stable()
                                    self.add_to_history("click_element", f"button: {identifier}", "success")
                                    return f"Successfully clicked job-level Easy Apply button"

                    # fallback click if identifier matches and isn't Easy Apply
                    if text and identifier.lower() in text.lower():
                        await button.click()
                        if post_click_selector:
                            try:
                                await self.page.wait_for_selector(post_click_selector, timeout=8000)
                            except:
                                print(f"⚠️ post_click_selector '{post_click_selector}' not found after click.")
                        await self.wait_for_page_stable()
                        self.add_to_history("click_element", f"button: {identifier}", "success")
                        return f"Successfully clicked button: {text}"


            error_msg = f"Error: Could not find {element_type} with identifier '{identifier}'"
            self.add_to_history("click_element", f"{element_type}: {identifier}", "failed")
            return error_msg

        except Exception as e:
            return f"Error clicking {element_type}: {str(e)}"


    @tool
    async def fill_input_field(field_identifier: str, value: str, field_type: str = "") -> str:
        """
        Fill an input field with a value
        
        Args:
            field_identifier: ID, name, or type of the input field
            value: Value to fill in the field
            field_type: Type of field (email, password, job_title, location, etc.)
        
        Returns:
            Success/failure message
        """
        try:
            if not await self.check_page_state():
                return "Error: Page not accessible"

            # Handle common autofill cases
            id_lower = field_identifier.lower()
            field_type_lower = field_type.lower()

            if field_type_lower == "email" or "email" in id_lower:
                value = LINKEDIN_EMAIL
                print(f"Value set to {value}")

            if field_type_lower == "password" or "password" in id_lower:
                value = LINKEDIN_PASSWORD
                print(f"Value set to {value}")

            if field_type_lower in ["job_title", "title", "role", "skill", "company"] or any(kw in id_lower for kw in ["job", "title", "skill", "company"]):
                value = JOB_TITLE  
                print(f"Value set to {value}")

            if field_type_lower == "location" or "location" in id_lower:
                value = JOB_LOCATION  
                print(f"Value set to {value}")
            
            if field_type_lower == "phone" or "phone" in id_lower:
                value = PHONE_NUMNER  
                print(f"Value set to {value}")


            print(f"🔧 Tool: Filling input field - {field_identifier}")
            print(f"   Value: {'*' * len(value) if 'password' in id_lower else value}")

            input_elem = None

            # Try multiple selector strategies
            selectors_to_try = [
                f'#{field_identifier}',
                f'[name="{field_identifier}"]',
                f'[placeholder*="{field_identifier}"]',
                f'[aria-label*="{field_identifier}"]'
            ]

            # Add known selectors for login and job search inputs
            if "email" in id_lower or "username" in id_lower:
                selectors_to_try.extend(['#username', '#session_key', '[name="session_key"]', 'input[type="email"]', '#email'])
            elif "password" in id_lower:
                selectors_to_try.extend(['#password', '[name="session_password"]', 'input[type="password"]'])
            elif field_type_lower in ["job_title", "title", "role", "skill", "company"] or any(kw in id_lower for kw in ["job", "title", "skill", "company"]):
                selectors_to_try.extend([
                    '[id*="search-box-keyword-id"]',
                    '[aria-label*="Search jobs"]',
                    '[placeholder*="Search jobs"]',
                    'input.jobs-search-box__text-input[role="combobox"]'
                ])
            elif "location" in id_lower or field_type_lower == "location":
                selectors_to_try.extend([
                    'input[placeholder*="Location"]',
                    '[aria-label*="Search location"]',
                    '[id*="search-box-location"]',
                    'input[id*="jobs-search-box-location"]'])
                
            elif "phone" in id_lower or field_type_lower == "phone":
                selectors_to_try.extend([
                    'input[id*="phoneNumber"]',
                    'input[id*="phone-number"]',
                    'input[id*="mobile"]',
                    'input[placeholder*="Phone"]',
                    'input[placeholder*="Mobile"]',
                    'input[aria-label*="Phone"]',
                    'input[aria-label*="Mobile"]',
                    'input[class*="phone"]',
                    'input[class*="mobile"]'
                ])

            for selector in selectors_to_try:
                try:
                    input_elem = await self.page.query_selector(selector)
                    if input_elem and await input_elem.is_visible():
                        break
                except:
                    continue

            if input_elem:
                await input_elem.click()
                await asyncio.sleep(0.5)
                await input_elem.fill(value)
                await asyncio.sleep(1)
                self.add_to_history("fill_input", f"{field_identifier} ({field_type})", "success")
                return f"Successfully filled input field: {field_identifier}"
            else:
                error_msg = f"Error: Could not find input field '{field_identifier}'"
                self.add_to_history("fill_input", f"{field_identifier} ({field_type})", "failed")
                return error_msg

        except Exception as e:
            return f"Error filling input field: {str(e)}"

    @tool
    async def press_enter_on_input(identifier: str, description: str = "") -> str:
        """
        Press the Enter key inside an input field (e.g. job title or location field).
        
        Args:
            identifier: A unique attribute of the input (e.g. id, placeholder, aria-label)
            description: Optional reason for pressing Enter

        Returns:
            Success/failure message
        """
        try:
            print(f"🔧 Tool: Pressing Enter in input: {identifier}")
            if description:
                print(f"   Reason: {description}")
            
            inputs = await self.page.query_selector_all('input')
            for input_elem in inputs:
                id_attr = await input_elem.get_attribute("id")
                aria_label = await input_elem.get_attribute("aria-label")
                placeholder = await input_elem.get_attribute("placeholder")

                if any(identifier.lower() in (val or "").lower() for val in [id_attr, aria_label, placeholder]):
                    await input_elem.focus()
                    await self.page.keyboard.press("Enter")
                    await self.wait_for_page_stable()
                    return f"Pressed Enter on input with identifier '{identifier}'"

            return f"Error: No input found matching identifier '{identifier}'"
        except Exception as e:
            return f"Error pressing Enter: {str(e)}"
    
    @tool
    async def navigate_to_url(url: str, description: str = "") -> str:
        """
        Navigate directly to a URL
        
        Args:
            url: URL to navigate to
            description: Optional description of why navigating to this URL
        
        Returns:
            Success/failure message
        """
        try:
            print(f"🔧 Tool: Navigating to URL - {url}")
            if description:
                print(f"   Reason: {description}")
            
            await self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await self.wait_for_page_stable()
            return f"Successfully navigated to: {url}"
            
        except Exception as e:
            return f"Error navigating to URL: {str(e)}"
        
    @tool
    async def wait_and_observe(seconds: int = 5, reason: str = "") -> str:
        """
        Wait for a specified number of seconds and observe page changes
        
        Args:
            seconds: Number of seconds to wait
            reason: Optional reason for waiting
        
        Returns:
            Status message
        """
        print(f"🔧 Tool: Waiting {seconds} seconds")
        if reason:
            print(f"   Reason: {reason}")
        
        await asyncio.sleep(seconds)
        return f"Waited {seconds} seconds"

    @tool
    async def check_page_status() -> str:
        """
        Check current page status and return information
        
        Returns:
            Current page information
        """
        try:
            current_url = self.page.url
            page_title = await self.page.title()
            
            status = f"Current URL: {current_url}\nPage Title: {page_title}"
            
            # Check if we're in jobs section
            if 'jobs' in current_url.lower() and 'linkedin.com' in current_url:
                status += "\n✅ Successfully reached LinkedIn Jobs section!"
            elif 'linkedin.com' in current_url and '/login' not in current_url:
                status += "\n✅ Successfully logged into LinkedIn"
            elif 'login' in current_url:
                status += "\n📝 On LinkedIn login page"
            
            return status
            
        except Exception as e:
            return f"Error checking page status: {str(e)}"
        
    @tool
    async def upload_resume_tool(element_id: str = "") -> str:
        """
        Uploads resume to a file input field on the page.

        Args:
            element_id: The ID of the file input element. If empty, will try to auto-detect.

        Returns:
            Upload status.
        """
        try:
            print(f"📎 [UploadResumeTool] Uploading resume from: {resume_path}")
            if not await self.check_page_state():
                return "Error: Page not accessible"

            input_elem = None

            if element_id:
                input_elem = await self.page.query_selector(f'#{element_id}')
            else:
                # Attempt auto-detection
                candidates = await self.page.query_selector_all('input[type="file"]')
                for c in candidates:
                    visible = await c.is_visible()
                    if visible:
                        input_elem = c
                        break

            if not input_elem:
                return "Error: No file input field found"

            await input_elem.set_input_files(self)
            await self.page.wait_for_timeout(1000)
            return "✅ Resume uploaded successfully"

        except Exception as e:
            return f"Error uploading resume: {str(e)}"

    return [click_element, fill_input_field, navigate_to_url, wait_and_observe, check_page_status, press_enter_on_input, form_fill_tool, upload_resume_tool]
