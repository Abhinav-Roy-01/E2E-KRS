"""
IndicTrans2 wrapper. Supports all 22 scheduled Indian languages <-> English.
Ported unchanged from the earlier working version -- this logic didn't need
to change in the rewrite, only where it's called from.

Setup note: pip install transformers torch IndicTransToolkit
Model weights download on first run (~2-4GB).
"""
from functools import lru_cache

LANG_CODE_MAP = {
    "ml": "mal_Mlym",
    "hi": "hin_Deva",
    "ta": "tam_Taml",
    "kn": "kan_Knda",
    "te": "tel_Telu",
    "bn": "ben_Beng",
    "en": "eng_Latn",
}


@lru_cache(maxsize=1)
def _load_model(source_lang: str):
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    from IndicTransToolkit.processor import IndicProcessor

    model_name = (
        "ai4bharat/indictrans2-en-indic-1B"
        if source_lang == "en"
        else "ai4bharat/indictrans2-indic-en-1B"
    )
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
    processor = IndicProcessor(inference=True)
    return tokenizer, model, processor


def translate(text: str, source_lang: str, target_lang: str) -> dict:
    """
    Returns {"translated_text": str, "confidence_score": float}.
    confidence_score is a placeholder length-ratio heuristic -- replace with
    a real quality-estimation signal (e.g. COMET-QE) before relying on it
    to gate human review in production.
    """
    if source_lang not in LANG_CODE_MAP or target_lang not in LANG_CODE_MAP:
        raise ValueError(f"Unsupported language pair: {source_lang} -> {target_lang}")

    tokenizer, model, processor = _load_model(source_lang)

    src_code = LANG_CODE_MAP[source_lang]
    tgt_code = LANG_CODE_MAP[target_lang]

    batch = processor.preprocess_batch([text], src_lang=src_code, tgt_lang=tgt_code)
    inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
    outputs = model.generate(**inputs, max_length=512, num_beams=5)
    decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
    translated = processor.postprocess_batch(decoded, lang=tgt_code)[0]

    length_ratio = len(translated) / max(len(text), 1)
    confidence = 1.0 if 0.5 <= length_ratio <= 2.0 else 0.5

    return {"translated_text": translated, "confidence_score": confidence}
