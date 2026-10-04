Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "T0tal: Rs l200 | Pald: 1000 | Due: 200"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: 12o0 | Paid: 1000 | Due: 200"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: 1NR12o0 | Paid: 1000 | Due: 200"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Tptol: 1200 | Pxid: 1000 | Due: 200"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: Rs. 1,20,000/- | Paid: Rs. 1,00,000/- | Due: Rs. 20,000/-"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: Rs 1250.50 | Paid: Rs 1000.25 | Due: Rs 250.25"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: 5000\nPaid: 2000\nDue: 3000"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: 1200 Paid: 1000 Due: 200"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Grand Total: 4500 | Advance: 1500 | Balance Due: 3000"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Due: Feb 13th, 2021 | Total: 8480 | Amount paid: 0 | Balance Due: 8480"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: 1200 | Paid: 1000 | Due: 300"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": ""}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Thank you for visiting"}' | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Consultation: 500"}' | ConvertTo-Json -Depth 5
