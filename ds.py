import re
import json
from openai import OpenAI

client = OpenAI(api_key="sk-77aed260437b44d3ad585f770c04a0ed", base_url="https://api.deepseek.com")

input_file = "/gemini/code/GuessBenchmark/data_generation/idiom.txt"  
compliant_output_file = "/gemini/code/GuessBenchmark/data_generation/chinese_idiom_emoji_by_ds.json"  
error_output_file = "/gemini/code/GuessBenchmark/data_generation/chinese_idiom_emoji_by_ds_error.json"  

json_pattern = re.compile(r'```json\s*({.*?})\s*```', re.DOTALL)


def process_response(idiom, response_content):
    # Try to extract JSON from the response
    json_match = json_pattern.search(response_content)
    
    if json_match:
        try:
            # Parse the JSON to validate it
            response_json = json.loads(json_match.group(1))
            if "emoji_rep" in response_json and "inference_chain" in response_json:
                # Valid format found
                with open(compliant_output_file, 'a', encoding='utf-8') as f:
                    json.dump(response_json, f, ensure_ascii=False)
                    f.write('\n')  
                return True
        except json.JSONDecodeError:
            pass
    
    # If we get here, either no JSON found or invalid format
    fail_data = {
        "idiom": idiom,
        "response": response_content
    }
    with open(error_output_file, 'a', encoding='utf-8') as f:
        json.dump(fail_data, f, ensure_ascii=False)
        f.write('\n') 
    return False

def main():
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            idioms = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return
    # Process each idiom
    for idiom in idioms:
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "You are a helpful assistant, capable of generating emoji representation sets for Chinese idioms. "
                            "Each set must contain exactly four emojis, with each emoji strictly corresponding to one of the four characters in the idiom IN SEQUENTIAL ORDER. "
                            "The corresponding emojis can follow either of these two rules: 1) The emoji represents a meaning that aligns with the character's meaning, or "
                            "2) The emoji's representation aligns with the pronunciation of the character. You may apply these two rules in any combination for each individual emoji in the set. "
                            "Additionally, your output must include both the final emoji result and the reasoning process behind generating the emoji set. "
                            "The output must be a single JSON object containing only the JSON and no additional text. "
                            "The JSON format should be: {\"emoji_rep\": \"xxxx\", \"inference_chain\": \"...\"}."
                        )
                    },
                    {
                        "role": "user", 
                        "content": f"Please generate a set of emojis for the idiom '{idiom}'"
                    },
                ],
                stream=False
            )
            # Process the response
            response_content = response.choices[0].message.content
            process_response(idiom, response_content)

        except Exception as e:
            print(f"Error processing idiom '{idiom}': {str(e)}")
            # Save the error case
            fail_data = {
                "idiom": idiom,
                "response": f"Error: {str(e)}"
            }
            with open(error_output_file, 'a', encoding='utf-8') as f:
                json.dump(fail_data, f, ensure_ascii=False)
                f.write('\n')

if __name__ == "__main__":
    main()