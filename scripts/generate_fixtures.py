import os
import sys
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.data_loader import DataLoader

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(base_dir, 'data')
    input_dir = os.path.join(base_dir, 'input')
    fixtures_dir = os.path.join(base_dir, 'tests', 'fixtures')
    
    os.makedirs(fixtures_dir, exist_ok=True)
    
    print("Loading data...")
    loader = DataLoader(data_dir)
    print("Data loaded and indexed.")
    
    fixtures = {}
    
    # Process first 3 cases
    for case_filename in ['EC_001.json', 'EC_002.json', 'EC_003.json']:
        input_path = os.path.join(input_dir, case_filename)
        if not os.path.exists(input_path):
            print(f"Warning: {input_path} does not exist.")
            continue
            
        with open(input_path, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
            
        case_id = case_data['case_id']
        order_id = case_data['customer_request']['claimed_order_id']
        request_message = case_data['customer_request']['message']
        
        print(f"Extracting facts for Case: {case_id}, Order: {order_id}")
        
        try:
            facts = loader.get_case_facts(case_id, request_message, order_id)
            fixtures[case_id] = facts.model_dump()
        except Exception as e:
            print(f"Error extracting facts for {case_id}: {e}")
            
    # Save to fixture file
    out_path = os.path.join(fixtures_dir, 'sample_orders.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)
        
    print(f"Saved fixtures to {out_path}")

if __name__ == '__main__':
    main()
