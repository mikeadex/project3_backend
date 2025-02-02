from cleaner import clean_text
import os

# Get the current directory and construct the absolute path to sample.txt
current_dir = os.path.dirname(os.path.abspath(__file__))
sample_file_path = os.path.join(current_dir, 'sample.txt')

with open(sample_file_path, 'r') as file:
    text = file.read()
    
class TestClass:
    pass

text_instance = TestClass()

cleaned_text = clean_text(text_instance, text)
print("Original text:")
print("-" * 50)
print(text)
print("\nCleaned text:")
print("-" * 50)
print(cleaned_text)