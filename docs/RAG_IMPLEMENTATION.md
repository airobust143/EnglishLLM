# RAG đang chạy trong repo

## Đánh giá dữ liệu

Bộ JSONL phù hợp làm nguồn RAG cho ba Unit: có ID ổn định, metadata bài/trang,
câu hỏi tách khỏi đáp án, và liên kết bài tập với đoạn đọc/quy tắc. Kiểm tra tự động
ghi nhận 106 bản ghi (30/37/39), gồm 73 bài tập, 18 văn bản, 12 tài liệu tham khảo
và 3 tổng quan. Không trùng ID; các liên kết `source_ids`, `see_also` và hint hợp lệ,
không vượt Unit. Không thấy nhãn `ANSWER:` trong `embed_text`.

Đây là kiểm tra cấu trúc, không chứng minh nội dung/đáp án hoặc số trang đúng với
sách gốc. Có 7 bản ghi tái dựng: U2-GS-02, U2-LISTENING-02, U2-WRITING-01,
U2-CLIL-01, U3-READING-01, U3-WRITING-02, U3-COMM-01. Tutor được yêu cầu nói rõ
điều này. Metadata API luôn có `page_verified: false`.

Ba file `rag_unit*.md` và `build_rag_jsonl.py` được mô tả trong README schema chưa
có trong repo. Hiện hãy sửa trực tiếp `rag_english10_global_success.jsonl` và chạy
validator bên dưới. Các file `unit-*.md` cũ không còn là nguồn đang truy xuất.
Không sửa corpus gốc trong lần tích hợp này.

## Luồng thực thi

1. `backend/services/corpus.py` nạp đúng `RAG_CORPUS`, kiểm tra schema, ID và liên
   kết. Cache theo đường dẫn, mtime nanosecond và kích thước; file đổi sẽ nạp lại.
   Dữ liệu lỗi trả HTTP 503, không âm thầm dùng corpus cũ hoặc quét toàn bộ docs.
2. `backend/services/retrieval.py` ưu tiên ID hoặc Unit + section + exercise/page.
   Số bài lấy từ `exercise`, không suy ra từ hậu tố ID (ví dụ U2-GS-02 là bài 3).
   Unit được nói rõ ưu tiên hơn tab giao diện. Bài số mơ hồ hỏi tên section bằng
   ngôn ngữ tự nhiên; người học không cần biết ID nội bộ. Nhiều Unit trong cùng
   câu hoặc bài không tồn tại mới trả yêu cầu làm rõ mà không gọi LLM.
3. Tìm kiến thức bằng BM25 trên `embed_text` + `search_aliases_vi`; chuẩn hóa dấu
   tiếng Việt và mở rộng một số cụm từ chủ đề. Câu hỏi quy tắc ưu tiên reference
   trong shortlist. Đây là lexical retrieval, chưa có embedding/reranker model.
   BM25 tính tần suất từ và độ dài tài liệu theo
   [mô tả trong Introduction to Information Retrieval](https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html).
4. Chỉ dùng lịch sử người học cho các lượt ngắn được nhận diện như `Why?`, `hint`,
   `hint 2`, `My answer: ...`. Ưu tiên bài được nhắc gần nhất; lời tutor không phải
   dữ liệu truy xuất. Câu hỏi chủ đề mới không kéo theo từ khóa của bài cũ.
5. Với bài xác định duy nhất, lấy thêm `source_ids` trước tài liệu `see_also`, trong
   ngân sách. `RAG_TOP_K` giới hạn kết quả tìm kiếm; bài xác định được thêm tối đa
   từng ấy nguồn liên quan. Văn bản dài được trích đoạn có nhãn `Partial excerpt`;
   câu hỏi giữ nguyên. Nguồn không vừa có thể bị bỏ; prompt yêu cầu không khẳng định
   đã đọc nguồn bắt buộc còn thiếu.
6. Chỉ `question`/`content` và metadata được đưa vào khối `student_visible`.
   Trước khi nộp bài, **không đưa** `answer`, `explanation`, `teacher_notes` vào
   prompt. Khi đã xác định duy nhất bài tập và có `attempt` hoặc `My answer: ...`,
   thêm `teacher_only` để chấm. `/document` không trả các trường dành cho tutor.
7. Prompt giữ nguyên từng khối JSON, dành ngân sách cho lịch sử ngắn hơn ở chế độ
   STUDY; không cắt chuỗi JSON ở giữa. Nếu bài chính không vừa, yêu cầu mở phiên mới
   hoặc tăng context. STUDY giữ câu hỏi, số thứ tự và xuống dòng khi stream;
   hội thoại thường vẫn dùng giới hạn câu cũ. Output vẫn tối đa 96 token mỗi lượt.

## Cách dùng và chỉnh sửa

Trong giao diện chat hiện có, chọn đúng Unit rồi nhập:

- `Unit 2 Speaking bài 1`
- `U1-GRAMMAR-01` rồi `hint` hoặc `hint 2`
- `My answer: 1. does` ở lượt tiếp theo để chấm bài đang làm
- `câu bị động` trong Unit 2 hoặc `động từ nguyên mẫu` trong Unit 3

API cũng nhận trường tùy chọn, không làm thay đổi client cũ:

```json
{"message":"Check item 1","unit":1,"exercise_id":"U1-GRAMMAR-01","attempt":"1. does"}
```

`POST /chat` trả thêm `sources` (ID, Unit, section, exercise, page, reconstructed,
source_file) của những nguồn thực sự được đóng gói và `response_mode`.
`POST /chat/stream` vẫn là plain text. `/health` và `/document` có thống kê corpus.

Chỉnh dữ liệu tại JSONL; chỉnh chính sách tại `backend/prompts/tutor.txt` rồi restart
backend. `.env` hỗ trợ `RAG_CORPUS`, `RAG_TOP_K=3`, `RAG_MAX_CONTEXT_CHARS=3000`.
Ngân sách context thực tế còn phụ thuộc `OLLAMA_NUM_CTX` và lịch sử. Số ký tự là
ước lượng, không phải tokenizer chính xác của model.

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -B -m evaluation.rag
```

Runner thứ hai kiểm tra corpus, 15 truy vấn mẫu, thời gian cold/warm và việc đóng
gói cả 73 bài ở hai giai đoạn: hỏi bài/chấm bài trong phiên mới. Không gọi model,
không tải embedding và không dùng dữ liệu người học.

Kết quả kiểm tra ngày 2026-11-02: 44/44 unit/integration tests qua; 15/15 probe
truy xuất đạt; không bài nào trong 73 bài bị chặn do ngân sách ở hai giai đoạn
trong phiên mới. Lần đo cuối: nạp corpus 8,963 ms; retrieval đã có cache trung vị
0,445 ms và p95 0,809 ms (130 lượt, 10 lượt mỗi probe). Các số này là phép đo local
nhỏ trong môi trường thực thi, có thể thay đổi theo máy/tải; không phải latency LLM.

## Phần cần đánh giá tiếp

- Đối chiếu 7 phần tái dựng, answer key và số trang với sách; bổ sung nguồn gốc.
- Viết hint riêng từng câu; hiện nhiều hint chỉ mô tả cách làm chung.
- Bổ sung truy vấn thật để đánh giá recall, đặc biệt cách diễn đạt tiếng Việt ngoài
  từ điển cụm từ hiện có. 13 probe là smoke test tự soạn, không phải held-out benchmark.
- Chấm chất lượng câu trả lời và đo end-to-end với Ollama thực tế. Các test API dùng
  model giả; thời gian retrieval không đại diện tốc độ sinh tiếng nói.
- Giấu trường answer ngăn việc đưa key sớm vào prompt; không bảo đảm model không tự
  suy ra đáp án từ câu hỏi/văn bản hoặc luôn tuân thủ hướng dẫn. Đây là tutor học tập,
  không phải cơ chế bảo mật đề thi. Corpus/hint mới vẫn cần người biên soạn duyệt.
