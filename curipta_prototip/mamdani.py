from typing import List
from models import NewsItem
from config import TRIGGERS, SOURCE_SCORES, WEIGHTS

class MamdaniScorer:
    def __init__(self):
        self.top_brands = {'apple', 'samsung', 'sony', 'lg', 'huawei', 'xiaomi', 'intel', 'amd', 'nvidia', 'qualcomm', 'google', 'microsoft', 'lenovo', 'dell', 'hp', 'asus', 'acer', 'msi'}

    def calculate_s1(self, item: NewsItem) -> float:
        t = item.title.lower()
        if any(b in t for b in self.top_brands): return WEIGHTS['S1']
        if any(b in item.source_url.lower() for b in self.top_brands): return WEIGHTS['S1'] * 0.7
        return 0.0

    def calculate_s2(self, item: NewsItem) -> float:
        t = item.title.lower()
        cnt = sum(1 for tr in TRIGGERS if tr in t)
        return WEIGHTS['S2'] * (0.5 if cnt == 1 else 0.8 if cnt == 2 else 1.0 if cnt > 2 else 0.0)

    def calculate_s3(self, item: NewsItem) -> float:
        u = item.source_url.lower()
        if any(x in u for x in ['vendor', 'official', 'press-release', 'bbci.co.uk']): return SOURCE_SCORES['vendor']
        if any(x in u for x in ['ixbt', 'habr', 'vc.ru', 'media', 'news']): return SOURCE_SCORES['media']
        return SOURCE_SCORES['blog']

    def mamdani_inference(self, s1: float, s2: float, s3: float) -> float:
        s1n, s2n, s3n = s1/WEIGHTS['S1'], s2/WEIGHTS['S2'], s3/WEIGHTS['S3']
        rules = [min(s1n, s2n) * 1.0, max(s1n, s2n) * 0.7, s3n * 0.5]
        return max(rules) * 100 if rules else 0.0

    def score_news(self, item: NewsItem) -> NewsItem:
        item.s1_score = self.calculate_s1(item)
        item.s2_score = self.calculate_s2(item)
        item.s3_score = self.calculate_s3(item)
        item.score = self.mamdani_inference(item.s1_score, item.s2_score, item.s3_score)
        item.is_important = item.score >= 60
        return item