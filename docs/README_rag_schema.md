# RAG tiếng Anh 10 Global Success: schema và cách dùng

> **Tích hợp trong repo:** Backend hiện dùng trực tiếp JSONL với metadata lookup + BM25,
> chưa dùng vector DB. Ba file `rag_unit*.md` và `build_rag_jsonl.py` bên dưới
> chưa có trong repo. Xem [RAG_IMPLEMENTATION.md](RAG_IMPLEMENTATION.md)
> để biết nguồn đang nạp, cách sửa, kiểm thử và giới hạn thực tế.

## 1. Các file
| File | Vai trò |
|---|---|
| `rag_unit1_family_life.md`, `rag_unit2_humans_and_environment.md`, `rag_unit3_music.md` | Nguồn gốc dễ đọc, dễ sửa tay (source of truth) |
| `build_rag_jsonl.py` | Script chuyển các file `.md` thành JSONL (chạy lại khi thêm unit) |
| `rag_english10_global_success.jsonl` | File đưa vào vector DB: 106 record (Unit 1: 30, Unit 2: 37, Unit 3: 39) |

Quy trình mở rộng: sửa hoặc thêm file `.md`, rồi chạy `python3 build_rag_jsonl.py`. Script tự kiểm tra trùng ID, thiếu câu hỏi/đáp án, tham chiếu sai, và đáp án lọt vào `embed_text`.

## 2. Các trường của một record

| Trường | Ý nghĩa | Dùng để |
|---|---|---|
| `id` | Mã duy nhất, ví dụ `U2-GRAMMAR-01` | Tra trực tiếp theo ID |
| `book`, `grade`, `unit`, `unit_title` | Sách, lớp, unit | Lọc metadata, mở rộng sang sách/lớp khác |
| `section`, `exercise`, `page` | Vị trí trong sách | Lọc, trả lời "bài 3 trang 22" |
| `skills`, `type`, `tags` | Kỹ năng, dạng bài, chủ điểm | Lọc, ghép bài tương tự |
| `chunk_kind` | `exercise` / `text` / `reference` / `overview` | Định tuyến |
| `embed_text` | Văn bản duy nhất dùng để **embed** (không chứa đáp án) | Vector search |
| `search_aliases_vi` | Từ khóa tiếng Việt (ngữ pháp, bài đọc, trang...) | BM25 / hybrid khi học sinh hỏi bằng tiếng Việt |
| `question` | Đề bài (học sinh được xem) | Hiển thị cho học sinh |
| `answer` | Đáp án hoặc câu trả lời mẫu | **Chỉ giáo viên (tutor) thấy**, dùng để chấm |
| `explanation` | Giải thích, dẫn chứng | Giải thích sau khi học sinh thử |
| `teacher_notes` | Ghi chú sửa lỗi sách, mẹo dạy | Chỉ cho tutor |
| `hints` | Gợi ý theo mức (level 1, 2) | Dạy theo từng bước |
| `content` | Nội dung hiển thị (bài đọc, hội thoại, script, glossary, quy tắc ngữ pháp) | Hiển thị và làm ngữ cảnh |
| `source_ids` | Chunk nguồn của bài (ví dụ bài đọc) | Nạp kèm khi giao bài |
| `see_also` | Chunk tham chiếu liên quan (ngữ pháp, từ vựng, mẫu câu) | Gợi ý level 2, ôn lại kiến thức |
| `reconstructed`, `reconstruction_note` | Phần dựng lại vì sách gốc là ảnh/bị thiếu | Dặn model nói thận trọng hơn |
| `answer_hidden` | `true` với bài tập | Cờ chặn lộ đáp án sớm |

## 3. Luồng truy xuất đề xuất
1. **Phân loại ý định:** hỏi bài cụ thể, hỏi kiến thức, xin luyện thêm, hay nộp bài để chấm.
2. **Viết lại câu hỏi** thành câu độc lập (dựa vào lịch sử hội thoại), có thể dịch sang tiếng Anh.
3. **Bài cụ thể** ("Unit 2 Speaking bài 1"): tra theo `unit`, `section`, `exercise`, hoặc theo ID. Không cần vector search.
4. **Hỏi kiến thức / tìm bài tương tự:** hybrid search = embedding trên `embed_text` + BM25 trên `embed_text` và `search_aliases_vi`; lọc theo `unit`, `skills`, `chunk_kind`.
5. **Rerank** top 20 còn 3-5.
6. Với bài tập được chọn: nạp thêm các chunk trong `source_ids` và `see_also`.
7. **Lắp ngữ cảnh** thành hai khối riêng (xem dưới), không trộn đáp án vào khối học sinh.

## 4. Gợi ý lắp ngữ cảnh và prompt cho tutor

```
<student_visible>
  (question / content / reference chunks)
</student_visible>

<teacher_only>
  (answer, explanation, teacher_notes: chỉ dùng để kiểm tra và giải thích)
</teacher_only>
```

Ý chính trong system prompt:
- Chỉ dùng nội dung trong ngữ cảnh. Không có thì nói "sách không đề cập", không bịa.
- Không nêu đáp án trước khi học sinh thử. Thứ tự: hỏi học sinh nghĩ gì, gợi ý level 1, level 2, giải thích một phần, rồi mới đưa đáp án.
- Khi chấm bài, so với `answer`. Giải thích lỗi sai bằng `explanation` và quy tắc trong `see_also`.
- Với chunk `reconstructed: true`, nói rõ "phần này được dựng lại, bạn nên đối chiếu với sách".
- Trích dẫn mã chunk khi cần (ví dụ `U2-GRAMMAR-01`).

## 5. Lưu ý và hạn chế
- `hints` hiện là **gợi ý mẫu theo dạng bài** (level 1) và chỉ tới tài liệu ôn (level 2). Chưa có gợi ý riêng cho từng câu. Có thể bổ sung sau bằng LLM hoặc viết tay vào trường `hints`.
- `search_aliases_vi` sinh bằng quy tắc (skill, section, trang, số bài), nên chưa có từ khóa nội dung tiếng Việt. Nếu học sinh hay hỏi bằng tiếng Việt, dùng embedding đa ngôn ngữ hoặc dịch câu hỏi sang tiếng Anh trước khi tìm.
- `see_also` ghép theo chủ điểm (`tags`) và kỹ năng, có thể có vài liên kết chưa sát; nên kiểm tra nhanh.
- Các chunk bị bỏ vì không có đáp án trong nguồn (xem ghi chú đầu mỗi file `.md`) không có trong JSONL.

## 6. Mở rộng sau này
- **Thêm unit:** viết `rag_unit4_*.md` theo định dạng chunk hiện có (mỗi chunk bắt đầu `## [ID]`, ngăn bằng `---`, có dòng metadata và nhãn `**Task:**`, `**ANSWER:**`, `**Explanation:**`), rồi chạy script.
- **Thêm sách hoặc lớp khác:** thêm chunk `OVERVIEW` có dòng `textbook:` của sách đó. Script lấy `book` từ đây; đổi trường `grade` trong script nếu không phải lớp 10.
- **Dữ liệu từ học sinh:** nên lưu riêng (lịch sử làm bài, lỗi hay sai), không trộn vào kho nội dung sách.
