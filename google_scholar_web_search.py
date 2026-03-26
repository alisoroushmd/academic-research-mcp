from bs4 import BeautifulSoup
import http_client
from scholarly import scholarly


def google_scholar_search(query, num_results=5):
    """
    Search Google Scholar using a simple keyword query.

    Parameters:
        query (str): The search query (e.g., paper title or author).
        num_results (int): The number of results to retrieve.

    Returns:
        list: A list of dictionaries containing search results.
    """
    search_url = f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = http_client.get(search_url, headers=headers)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    results = []
    count = 0

    for item in soup.find_all('div', class_='gs_ri'):
        if count >= num_results:
            break
        title_tag = item.find('h3', class_='gs_rt')
        title = title_tag.get_text() if title_tag else 'No title available'
        link = title_tag.find('a')['href'] if title_tag and title_tag.find('a') else 'No link available'
        authors_tag = item.find('div', class_='gs_a')
        authors = authors_tag.get_text() if authors_tag else 'No authors available'
        abstract_tag = item.find('div', class_='gs_rs')
        abstract = abstract_tag.get_text() if abstract_tag else 'No abstract available'
        results.append({
            'title': title,
            'authors': authors,
            'abstract': abstract,
            'url': link
        })
        count += 1

    return results


def advanced_google_scholar_search(query, author=None, year_range=None, num_results=5):
    """
    Search Google Scholar using advanced filters (author, year range).

    Parameters:
        query (str): The search query.
        author (str): Author name filter.
        year_range (tuple): (start_year, end_year) filter.
        num_results (int): Number of results to retrieve.

    Returns:
        list: A list of dictionaries containing search results.
    """
    search_url = "https://scholar.google.com/scholar?"
    search_params = {'q': query.replace(' ', '+')}
    if author:
        search_params['as_auth'] = author
    if year_range:
        start_year, end_year = year_range
        search_params['as_ylo'] = start_year
        search_params['as_yhi'] = end_year

    search_url += '&'.join([f"{key}={value}" for key, value in search_params.items()])
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = http_client.get(search_url, headers=headers)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    results = []
    count = 0

    for item in soup.find_all('div', class_='gs_ri'):
        if count >= num_results:
            break
        title_tag = item.find('h3', class_='gs_rt')
        title = title_tag.get_text() if title_tag else 'No title available'
        link = title_tag.find('a')['href'] if title_tag and title_tag.find('a') else 'No link available'
        authors_tag = item.find('div', class_='gs_a')
        authors = authors_tag.get_text() if authors_tag else 'No authors available'
        abstract_tag = item.find('div', class_='gs_rs')
        abstract = abstract_tag.get_text() if abstract_tag else 'No abstract available'
        results.append({
            'title': title,
            'authors': authors,
            'abstract': abstract,
            'url': link
        })
        count += 1

    return results
