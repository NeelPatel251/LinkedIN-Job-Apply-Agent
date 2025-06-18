from urllib.parse import quote_plus


def format_linkedin_job_url(base_url: str, job_title: str, location: str, easy_apply: bool = True) -> str:
    """
    Format LinkedIn job search URL with proper URL encoding.

    Args:
        base_url (str): Base LinkedIn URL
        job_title (str): Job title to search for
        location (str): Location to search in
        easy_apply (bool): Whether to filter for Easy Apply jobs

    Returns:
        str: Formatted LinkedIn job search URL
    """
    encoded_keywords = quote_plus(job_title)
    encoded_location = quote_plus(location)

    job_search_url = f"{base_url}/jobs/search"
    params = []

    if easy_apply:
        params.append("f_AL=true")
    params.append(f"keywords={encoded_keywords}")
    params.append(f"location={encoded_location}")

    query_string = "&".join(params)
    return f"{job_search_url}?{query_string}"
