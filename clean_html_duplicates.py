
import os
import glob

def clean_duplicates():
    files = glob.glob("outputs/*/index.html")
    print(f"Found {len(files)} index.html files.")
    
    count = 0
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        modified = False
        
        # Strategy: Rename startPay to startCryptoPay in the injected widget code.
        # Unique identifier for injected code: setStatus("주문 생성 중..."); inside startPay
        
        if 'async function startPay() {' in content and 'setStatus("주문 생성 중...");' in content:
            # Check if they are close (to be sure)
            idx_fn = content.rfind('async function startPay() {') # Use rfind because injected is usually at the end
            idx_status = content.find('setStatus("주문 생성 중...");', idx_fn)
            
            if idx_fn != -1 and idx_status != -1 and (idx_status - idx_fn) < 200:
                print(f"[{file_path}] Renaming startPay to startCryptoPay...")
                
                # We need to be careful not to replace the OTHER startPay if it exists earlier.
                # So we replace only this occurrence.
                
                # Construct the old string chunk to replace
                old_chunk_sig = 'async function startPay() {'
                new_chunk_sig = 'async function startCryptoPay() {'
                
                # We will split the content at idx_fn and replace the first occurrence in the second part?
                # No, just string slicing.
                
                pre = content[:idx_fn]
                post = content[idx_fn + len(old_chunk_sig):]
                content = pre + new_chunk_sig + post
                
                # Now also update the event listener
                # It usually appears after the function definition in the injected block.
                # Look for 'payBtn.addEventListener("click", startPay);'
                
                listener_old = 'payBtn.addEventListener("click", startPay);'
                listener_new = 'payBtn.addEventListener("click", startCryptoPay);'
                
                if listener_old in content:
                    content = content.replace(listener_old, listener_new)
                    modified = True
                else:
                    print(f"[{file_path}] WARNING: Event listener not found or already updated.")
                    # It might be formatted differently? 
                    # If not found, we might have broken the button. 
                    # But let's assume it matches the injection template.
                    # If it fails, we will see errors in QA.
                    pass
            else:
                 print(f"[{file_path}] startPay found but not close to setStatus. Skipping.")

        if modified:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            count += 1
            
    print(f"Fixed {count} files.")

if __name__ == "__main__":
    clean_duplicates()
