import requests
import xml.etree.ElementTree as ET

class NewsParserService:
    def __init__(self):
        self.rss_url = "https://cointelegraph.com/rss"

    def get_latest_news(self):
        """Fetches the latest crypto news from RSS."""
        try:
            response = requests.get(self.rss_url)
            root = ET.fromstring(response.content)
            news_items = []
            
            # Extract the top 5 news items
            for item in root.findall('.//item')[:5]:
                news_items.append({
                    'title': item.find('title').text,
                    'link': item.find('link').text,
                    'pubDate': item.find('pubDate').text
                })
            return news_items
        except Exception as e:
            print(f"Error fetching news: {e}")
            return []
