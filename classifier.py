import logging
from typing import List, Dict, Any, Union

from transformers import pipeline

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default labels for zero-shot classification
DEFAULT_LABELS = [
    "sports news",
    "broadcast information",
    "technical documentation",
    "production metadata",
    "industry news",
    "entertainment"
]

class ContentClassifier:
    """Class for classifying text content."""
    
    def __init__(self, model_name: str = "facebook/bart-large-mnli", labels: List[str] = None):
        """
        Initialize the content classifier.
        
        Args:
            model_name: The name of the Hugging Face model to use
            labels: List of classification labels. If None, uses DEFAULT_LABELS
        """
        self.labels = labels or DEFAULT_LABELS
        
        logger.info(f"Loading classification model: {model_name}")
        try:
            self.classifier = pipeline(
                "zero-shot-classification",
                model=model_name
            )
            logger.info("Classification model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading classification model: {e}")
            raise
    
    def classify_text(self, text: str, labels: List[str] = None) -> Dict[str, Any]:
        """
        Classify the given text.
        
        Args:
            text: The text to classify
            labels: Optional list of labels to use for this classification.
                   If None, uses the labels provided during initialization.
        
        Returns:
            Dictionary containing classification results with labels and scores
        """
        if not text:
            logger.warning("Empty text provided for classification")
            return {"labels": [], "scores": []}
        
        # Use provided labels or fall back to default
        classification_labels = labels or self.labels
        
        try:
            # Truncate text if it's too long (model dependent)
            max_length = 1024  # Adjust based on model requirements
            truncated_text = text[:max_length] if len(text) > max_length else text
            
            # Perform classification
            result = self.classifier(
                truncated_text,
                candidate_labels=classification_labels,
                multi_label=True
            )
            
            logger.info(f"Text classified with top label: {result['labels'][0]}")
            return {
                "labels": result["labels"],
                "scores": result["scores"]
            }
        except Exception as e:
            logger.error(f"Error classifying text: {e}")
            return {"labels": [], "scores": []}
    
    def get_top_label(self, text: str, threshold: float = 0.3) -> Union[str, None]:
        """
        Get the top classification label for the given text.
        
        Args:
            text: The text to classify
            threshold: Minimum confidence score threshold
        
        Returns:
            The top label if its score is above the threshold, otherwise None
        """
        result = self.classify_text(text)
        
        if result["labels"] and result["scores"] and result["scores"][0] >= threshold:
            return result["labels"][0]
        
        return None
    
    def get_all_labels_above_threshold(self, text: str, threshold: float = 0.3) -> List[str]:
        """
        Get all labels with scores above the threshold.
        
        Args:
            text: The text to classify
            threshold: Minimum confidence score threshold
        
        Returns:
            List of labels with scores above the threshold
        """
        result = self.classify_text(text)
        
        labels_above_threshold = []
        for label, score in zip(result["labels"], result["scores"]):
            if score >= threshold:
                labels_above_threshold.append(label)
        
        return labels_above_threshold

# Singleton instance for reuse
_classifier_instance = None

def get_classifier(model_name: str = "facebook/bart-large-mnli", labels: List[str] = None) -> ContentClassifier:
    """
    Get or create a ContentClassifier instance.
    
    Args:
        model_name: The name of the Hugging Face model to use
        labels: List of classification labels
    
    Returns:
        ContentClassifier instance
    """
    global _classifier_instance
    
    if _classifier_instance is None:
        _classifier_instance = ContentClassifier(model_name, labels)
    
    return _classifier_instance

def classify_text(text: str, labels: List[str] = None) -> Dict[str, Any]:
    """
    Classify the given text using the default classifier.
    
    Args:
        text: The text to classify
        labels: Optional list of labels to use for this classification
    
    Returns:
        Dictionary containing classification results
    """
    classifier = get_classifier()
    return classifier.classify_text(text, labels)

if __name__ == "__main__":
    # Simple test
    test_text = "The game last night was incredible with a last-minute goal securing the championship."
    print(f"Testing classification with text: '{test_text}'")
    
    classifier = get_classifier()
    result = classifier.classify_text(test_text)
    
    print("\nClassification results:")
    for label, score in zip(result["labels"], result["scores"]):
        print(f"{label}: {score:.4f}")
    
    top_label = classifier.get_top_label(test_text)
    print(f"\nTop label: {top_label}")
    
    labels_above_threshold = classifier.get_all_labels_above_threshold(test_text, threshold=0.2)
    print(f"\nLabels above threshold (0.2): {labels_above_threshold}")
