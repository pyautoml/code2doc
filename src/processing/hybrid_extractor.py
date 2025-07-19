#!/usr/bin/env python3

import re
import spacy
from diskcache import Cache
from keybert import KeyBERT
from typing import List, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer


class SemanticKeywordExtractor:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm", exclude=["parser", "ner"])
        self.kw_model = KeyBERT(model="all-MiniLM-L6-v2")  # 80MB model
        self.tfidf = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")

    cache = Cache("keyword_cache")

    @cache.memoize()
    def get_keywords(self, text: str, top_n: int = 10) -> List[Tuple[str, float]]:
        return self.extract_keywords(text, top_n)

    def extract_keywords(self, text: str, top_n: int = 10) -> List[Tuple[str, float]]:
        doc = self.nlp(self._preprocess_text(text))
        candidates = self._get_candidates(doc)
        try:
            keywords = self.kw_model.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 2),
                stop_words="english",
                candidates=candidates,
                top_n=top_n,
            )
            if len(keywords) >= top_n // 2:
                return keywords
        except:
            pass

        tfidf_scores = self._get_tfidf_scores(text, candidates)
        return sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    @staticmethod
    def _preprocess_text(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        return re.sub(r"[^\w\s-]", " ", text)

    @staticmethod
    def _get_candidates(doc) -> List[str]:
        candidates = set()
        for token in doc:
            if (
                token.pos_ in ["NOUN", "PROPN"]
                and len(token.text) > 2
                and not token.is_stop
            ):
                lemma = token.lemma_.lower().strip()
                candidates.add(lemma)

                if token.ent_type_:
                    candidates.add(token.text.lower())
        return list(candidates)

    def _get_tfidf_scores(self, text: str, candidates: List[str]) -> dict:
        self.tfidf.fit([text])
        features = self.tfidf.get_feature_names_out()
        scores = self.tfidf.transform([text]).toarray()[0]
        return {
            features[i]: scores[i]
            for i in range(len(features))
            if features[i] in candidates
        }
