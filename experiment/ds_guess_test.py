import re
import json
from openai import OpenAI

from dotenv import load_dotenv
import os

load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("DS_API_KEY"), base_url=os.getenv("DS_URL"))

# File paths
input_file = "/data/tianyu_data/appendix/GuessBenchmark/data_generation/pop_idioms_emoji_pair/idiom_emoji_1_500_by_ds_fixed.json"  
output_file = "/data/tianyu_data/appendix/GuessBenchmark/experiment/output/idiom_emoji_1_500_by_ds_fixed_by_ds.json"  
error_output_file = "/data/tianyu_data/appendix/GuessBenchmark/experiment/output/idiom_emoji_1_500_by_ds_fixed_by_ds_error.json"  

# Regular expression pattern to extract JSON from response
json_pattern = re.compile(r'```json\s*({.*?})\s*```', re.DOTALL)

def process_response(idiom_gt, emoji_rep, response_content):
    """Process the API response and save to appropriate file based on content."""
    # Try to extract JSON from the response
    json_match = json_pattern.search(response_content)
    
    if json_match:
        try:
            # Parse the JSON to validate it
            response_json = json.loads(json_match.group(1))
            if "idiom" in response_json and "inference_chain" in response_json:
                # Create new JSON with idiom as first element
                compliant_data = {
                    "gt": idiom_gt,
                    "pred": response_json["idiom"],
                    "emoji_rep": emoji_rep,
                    "inference_chain": response_json["inference_chain"]
                }
                # Valid format found
                with open(output_file, 'a', encoding='utf-8') as f:
                    json.dump(compliant_data, f, ensure_ascii=False)
                    f.write('\n') 
                return True
        except json.JSONDecodeError:
            pass
    
    # If we get here, either no JSON found or invalid format
    fail_data = {
        "gt": idiom_gt,
        "response": response_content
    }
    with open(error_output_file, 'a', encoding='utf-8') as f:
        json.dump(fail_data, f, ensure_ascii=False)
        f.write('\n')  
    return False

def main():
    # Read idioms from file
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)  
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: File '{input_file}' is not a valid JSON file.")
        return
    except KeyError:
        print(f"Error: Some entries in '{input_file}' are missing the 'word' field.")
        return
    
    # Initialize counters
    correct_cnt = 0
    wrong_cnt = 0

    # Process each idiom with progress tracking
    for index, item in enumerate(data, start=1):
        try:
            # Print progress
            idiom = item["idiom"]
            emoji_rep = item["emoji_rep"]
            print(f"Processing idiom {index}/{len(data)}: {idiom}", end=" - ")
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are a linguistic expert tasked with identifying Chinese four-character idioms (成语) based on a set of four emojis "
                            "Each emoji corresponds to one character in the idiom, in sequential order. The mapping can be either:"
                            "1)Semantic Match: The emoji's meaning aligns with the character's meaning."
                            "2)Phonetic Match: The emoji's Chinese pronunciation (pinyin) matches or closely resembles the character's pronunciation."
                            "Additionally, your output must include both the final idiom result and the reasoning process. "
                            "The output must be a single JSON object containing only the JSON and no additional text. "
                            "The JSON format should be: {\"idiom\": \"xxxx\", \"inference_chain\": \"...\"}."
                        )
                    },
                    {
                        "role": "user", 
                        "content": f"'{emoji_rep}'"
                    },
                ],
                stream=False
            )
            
            # Process the response
            response_content = response.choices[0].message.content
            success = process_response(idiom, emoji_rep, response_content)
            print(f"Success: {success}")
            
            # Flush writes to ensure data is saved
            if success:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.flush()
                correct_cnt += 1
            else:
                with open(error_output_file, 'a', encoding='utf-8') as f:
                    f.flush()
                wrong_cnt += 1
            
        except Exception as e:
            print(f"Error: {str(e)}")
            # Save the error case
            fail_data = {
                "idiom": idiom,
                "response": f"Error: {str(e)}"
            }
            with open(error_output_file, 'a', encoding='utf-8') as f:
                json.dump(fail_data, f, ensure_ascii=False)
                f.write('\n')
                f.flush()
    print(f"Correct: {correct_cnt} | Wrong: {wrong_cnt}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. All completed items have been saved.")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
        print("All completed items have been saved.")