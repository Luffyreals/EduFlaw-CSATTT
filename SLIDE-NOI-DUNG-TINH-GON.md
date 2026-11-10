# NỘI DUNG SLIDE THUYẾT TRÌNH BTL AN TOÀN THÔNG TIN (ĐÃ TINH GỌN)

> **Dự án:** EduFlaw — Kiểm Thử & Phòng Thủ Bảo Mật Ứng Dụng Web  
> **Nhóm 7 (hoặc Nhóm 5) — Khóa D24 — PTIT Hà Nội**  
> **GVHD:** ThS. Đỗ Xuân Chợ  
> **Tiêu chí tối ưu:** Giảm tối đa chữ thừa, dùng từ ngữ bình dân dễ hiểu, bỏ bớt thuật ngữ phức tạp, chuẩn form slide trình chiếu.

---

### SLIDE 1: TRANG TIÊU ĐỀ
* **Tiêu đề lớn:** EduFlaw — Kiểm Thử & Phòng Thủ Bảo Mật Ứng Dụng Web
* **Môn học:** Cơ sở An toàn thông tin
* **Giảng viên hướng dẫn:** ThS. Đỗ Xuân Chợ
* **Thành viên nhóm:** Nguyễn Hoàng Tùng · Nguyễn Bá Minh Đức · Trần Anh Tú · Bùi Minh Khang
* **Công nghệ sử dụng:** Python (Flask), MySQL, Bootstrap
> 🎙️ **Lời nói:** *"Kính thưa Thầy và các bạn, hôm nay nhóm em xin trình bày bài tập lớn môn Cơ sở An toàn thông tin với đề tài: Kiểm thử và xây dựng giải pháp phòng thủ bảo mật cho hệ thống quản lý đào tạo EduFlaw."*

---

### SLIDE 2: MỤC LỤC BÁO CÁO
* **01. Giới thiệu dự án:** Hệ thống EduFlaw và mục tiêu kép
* **02. Phân quyền người dùng:** 3 vai trò và ranh giới quyền hạn
* **03. Phương pháp kiểm thử:** Kết hợp kiểm tra tự động và rà soát thủ công
* **04. Các kịch bản tấn công:** Các nguy cơ bảo mật theo chuẩn OWASP 2025
* **05. Giải pháp phòng thủ & Kết quả:** Cách khắc phục từ gốc và bài học thực tế
> 🎙️ **Lời nói:** *"Bài báo cáo của nhóm gồm 5 phần chính: từ khâu phân tích hệ thống, tìm kiếm lỗ hổng, thực hiện tấn công kiểm chứng, cho đến các giải pháp phòng thủ cụ thể."*

---

### SLIDE 3: CHUYỂN PHẦN 1
* **PHẦN 01: GIỚI THIỆU DỰ ÁN**
* EduFlaw là gì, mục tiêu xây dựng và công nghệ nền tảng.
> 🎙️ **Lời nói:** *"Đầu tiên, em xin giới thiệu tổng quan về hệ thống EduFlaw và lý do nhóm chọn đề tài này."*

---

### SLIDE 4: TỔNG QUAN HỆ THỐNG EDUFLAW
* **Bản chất hệ thống:**
  * Cổng quản lý đào tạo đại học thực tế (hồ sơ, điểm số, lớp tín chỉ, lịch học).
  * Xây dựng trên nền tảng Python Flask và cơ sở dữ liệu MySQL.
* **Hai mục tiêu cốt lõi:**
  1. **Một sản phẩm chạy thật:** Đầy đủ nghiệp vụ quản lý đào tạo cho nhà trường.
  2. **Một môi trường thực nghiệm an toàn thông tin:** Áp dụng chuẩn bảo mật mới nhất OWASP Top 10:2025.
> 🎙️ **Lời nói:** *"EduFlaw không chỉ là một bài tập làm web thông thường mà là một ứng dụng chạy thật, được nhóm sử dụng làm môi trường thực nghiệm để săn tìm và vá các lỗ hổng an toàn thông tin."*

---

### SLIDE 5: CHUYỂN PHẦN 2
* **PHẦN 02: VAI TRÒ & PHÂN QUYỀN**
* Ai được làm gì trên hệ thống — Tuyến phòng thủ đầu tiên.
> 🎙️ **Lời nói:** *"Phần tiếp theo là mô hình phân quyền — yếu tố quan trọng nhất để ngăn chặn người dùng làm việc ngoài quyền hạn của mình."*

---

### SLIDE 6: MA TRẬN PHÂN QUYỀN — 3 VAI TRÒ
* **👑 Quản trị viên (Master):**
  * Toàn quyền quản trị: Quản lý sinh viên, giảng viên, lớp học và giám sát nhật ký.
* **👨‍🏫 Giảng viên (Lecturer / Advisor):**
  * Chỉ được nhập/sửa điểm lớp mình dạy.
  * Chỉ xem danh sách sinh viên lớp mình làm cố vấn.
* **🎓 Sinh viên (Student):**
  * Chỉ xem điểm số, lịch học và hồ sơ của chính mình.
* **Nguyên tắc vàng:** Máy chủ tự kiểm tra quyền ở từng thao tác, không tin tưởng giao diện bên ngoài.
> 🎙️ **Lời nói:** *"Hệ thống chia làm 3 vai trò rõ rệt. Quan trọng nhất: Giảng viên không được sửa điểm lớp người khác, và Sinh viên tuyệt đối không thể xem trộm thông tin của bạn học."*

---

### SLIDE 7: BẢNG PHÂN QUYỀN CHI TIẾT
* **Hồ sơ sinh viên:** Quản trị toàn quyền · Giảng viên chỉ xem lớp cố vấn · Sinh viên chỉ xem của mình.
* **Điểm thi:** Giảng viên chỉ sửa lớp mình dạy · Sinh viên chỉ xem điểm của mình.
* **Tài khoản & Phân công:** Chỉ Quản trị viên tối cao mới có quyền thêm/bớt và khóa tài khoản.
* **Thời khóa biểu:** Tự động hiển thị đúng người, đúng lớp.
> 🎙️ **Lời nói:** *"Bảng phân quyền này đảm bảo nguyên tắc: mỗi người chỉ nhìn thấy và thao tác đúng phần dữ liệu thuộc phạm vi công việc của mình."*

---

### SLIDE 8: CHUYỂN PHẦN 3
* **PHẦN 03: PHƯƠNG PHÁP KIỂM THỬ**
* Chủ động tìm lỗ hổng trước khi kẻ xấu tìm ra.
> 🎙️ **Lời nói:** *"Để kiểm tra độ an toàn của EduFlaw, nhóm đã kết hợp hai phương pháp: kiểm tra tự động và rà soát thủ công."*

---

### SLIDE 9: HAI PHƯƠNG PHÁP KIỂM THỬ
* **Kiểm tra tự động (Tool quét):**
  * Dùng chương trình tự động dội hàng loạt dữ liệu lạ và thử mật khẩu liên tục.
  * *Điểm mạnh:* Tốc độ nhanh, tìm ra các chỗ thiếu bảo vệ và các lỗi làm sập phần mềm.
* **Rà soát thủ công (Đọc mã nguồn bằng mắt):**
  * Đọc từng dòng code, tự đổi các thông số trên đường link để kiểm tra logic.
  * *Điểm mạnh:* Bắt được các lỗi logic nghiệp vụ mà máy móc tự động không thể hiểu được.
> 🎙️ **Lời nói:** *"Công cụ tự động giúp nhóm quét nhanh trên diện rộng, còn việc soi mã bằng tay giúp phát hiện các lỗi logic phân quyền tinh vi."*

---

### SLIDE 10: QUY TRÌNH 4 BƯỚC CỦA NHÓM
1. **Soi mã nguồn:** Tìm những chỗ nhận dữ liệu từ người dùng và chỗ gọi thư viện ngoài.
2. **Dựng bản có lỗi:** Tạo nhánh thử nghiệm để tái hiện đúng nguy cơ.
3. **Tấn công thật:** Thử xem trộm điểm, thử dò mật khẩu, thử bơm dữ liệu dị dạng.
4. **Vá lỗi & Kiểm tra lại:** Sửa code ở bản chính thức và chạy bộ test tự động để đảm bảo không bị lỗi lại.
> 🎙️ **Lời nói:** *"Nhóm làm việc theo quy trình khép kín: Tìm điểm yếu -> Khai thác thật để thấy hậu quả -> Vá từ gốc -> Viết bài test để bảo vệ lâu dài."*

---

### SLIDE 11: BẰNG CHỨNG THỰC NGHIỆM BẰNG CON SỐ
* **69 đường dẫn web:** Tự động rà quét toàn bộ hệ thống; phát hiện 23 trang bảo mật và 1 trang debug mở trong lúc làm.
* **23 mẫu dữ liệu độc hại:** Bơm vào cổng xác thực $\rightarrow$ **0 lỗi sập máy chủ** (nguyên tắc xử lý lỗi an toàn).
* **Dò mật khẩu liên tiếp:** Hệ thống cho thử 4 lần, **đúng lần thứ 5 là khóa chặt** trong 60 giây.
> 🎙️ **Lời nói:** *"Mọi đánh giá của nhóm đều dựa trên số liệu thực tế đo đạc được, chứng minh hệ thống có cơ chế tự vệ rõ ràng."*

---

### SLIDE 12: KẾT QUẢ ĐỐI CHỨNG — CHỐNG DÒ MẬT KHẨU
* **Bản chưa vá (Nguy hiểm):**
  * Kẻ xấu dùng phần mềm thử 12 mật khẩu liên tiếp mà không bị chặn $\rightarrow$ Rất dễ bị mất tài khoản.
* **Bản đã vá (An toàn):**
  * Thử sai đến lần thứ 5 $\rightarrow$ Máy chủ lập tức khóa quyền truy cập trong 60 giây.
  * Khóa đồng thời cả địa chỉ mạng (IP) và tên tài khoản.
> 🎙️ **Lời nói:** *"Sự khác biệt rõ ràng nhất là: trước khi vá thì hacker có thể thử mật khẩu thoải mái; sau khi vá, chỉ cần gõ sai 5 lần là hệ thống đóng sập cửa bảo vệ ngay."*

---

### SLIDE 13: SỰ BÙ TRỪ GIỮA TỰ ĐỘNG VÀ THỦ CÔNG
* **Công cụ tự động làm tốt:**
  * Dội hàng trăm request trong vài giây để kiểm tra khóa tài khoản.
  * Thử các ký tự dị dạng để xem phần mềm có bị văng lỗi không.
  * Quét nhanh các đường dẫn bị lộ.
* **Con người làm tốt:**
  * Nhận biết khi nào việc xem dữ liệu là trái phép (máy chủ báo thành công nhưng thực ra đang lộ điểm người khác).
  * Rà soát từng đường link thư viện mượn từ bên ngoài.
> 🎙️ **Lời nói:** *"Máy móc giúp tiết kiệm thời gian quét diện rộng, còn con người phán đoán nghiệp vụ — cả hai bù trừ hoàn hảo cho nhau."*

---

### SLIDE 14: CHUYỂN PHẦN 4
* **PHẦN 04: CÁC CÁCH TẤN CÔNG**
* Điều gì xảy ra khi các ranh giới an toàn bị phá vỡ?
> 🎙️ **Lời nói:** *"Sau đây, nhóm xin trình bày chi tiết 4 nhóm nguy cơ chính theo chuẩn bảo mật mới nhất OWASP 2025."*

---

### SLIDE 15: BỐN NHÓM NGUY CƠ TRỌNG TÂM (OWASP 2025)
* **A01 — Lỗi phân quyền:** Người dùng làm được việc ngoài quyền hạn (xem trộm điểm, sửa trộm điểm).
* **A03 — Thư viện bên ngoài bị cài cắm mã độc (MỚI 2025):** Thư viện mượn từ trên mạng bị kẻ gian chiếm quyền và sửa đổi.
* **A07 — Lỗi đăng nhập & xác thực:** Dò mật khẩu liên tục không bị chặn; đổi mật khẩu xong người cũ vẫn vào được.
* **A10 — Xử lý sai khi gặp sự cố (MỚI 2025):** Khi phần mềm gặp lỗi thì làm lộ thông tin nhạy cảm hoặc mở toang cửa cho người ngoài.
> 🎙️ **Lời nói:** *"Nhóm tập trung vào 4 nhóm lỗ hổng thực tế nhất: Lỗi phân quyền, Nguy cơ từ thư viện mượn ngoài, Lỗi đăng nhập, và Cách xử lý khi hệ thống gặp sự cố."*

---

### SLIDE 16: CÁC KỸ THUẬT KHAI THÁC TRÊN EDUFLAW
* **Đổi số trên đường link (IDOR):** Sinh viên sửa số ID trên thanh địa chỉ để xem trộm bảng điểm của bạn khác.
* **Vượt quyền giảng viên:** Giảng viên tự ý sửa điểm lớp của đồng nghiệp.
* **Đầu độc thư viện mạng:** Kẻ xấu sửa file JavaScript trên mạng để nghe lén mật khẩu khi sinh viên đăng nhập.
* **Dò mật khẩu tự động:** Dùng máy tính thử liên tục hàng chục mật khẩu thông dụng.
* **Ép máy chủ báo lỗi:** Gửi dữ liệu phá hoại để bắt máy chủ in mã nguồn ra màn hình.
> 🎙️ **Lời nói:** *"Đây là 5 kỹ thuật tấn công phổ biến mà bất kỳ kẻ tấn công nào cũng sẽ thử đầu tiên khi nhắm vào một trang web trường học."*

---

### SLIDE 17: QUY TRÌNH KẺ XẤU TẤN CÔNG HỆ THỐNG
* **Bước 1:** Dò mật khẩu đăng nhập của một tài khoản sinh viên bất kỳ.
* **Bước 2:** Vào trang xem điểm, thử đổi số trên đường dẫn để đọc thông tin và số CCCD của bạn học.
* **Bước 3:** Thử gõ trực tiếp đường dẫn trang quản trị để tìm cách chiếm quyền Admin.
* **Bước 4:** Gửi ký tự lạ để ép phần mềm báo lỗi nhằm tìm hiểu cấu trúc cơ sở dữ liệu bên trong.
* **Mục tiêu cần bảo vệ:** Điểm thi, số CCCD, tài khoản và sự toàn vẹn của hệ thống.
> 🎙️ **Lời nói:** *"Kịch bản tấn công thường đi từng bước: từ việc chiếm tài khoản quyền thấp, đến việc lần mò xem trộm dữ liệu người khác và tìm cách chiếm quyền cao nhất."*

---

### SLIDE 18: CHUYỂN PHẦN 5
* **PHẦN 05: CÁCH PHÒNG THỦ**
* Vá lỗi từ gốc và giải thích vì sao giải pháp có hiệu quả.
> 🎙️ **Lời nói:** *"Để chống lại các nguy cơ trên, nhóm đã xây dựng các lớp phòng thủ đồng bộ từ giao diện, mã nguồn đến cơ sở dữ liệu."*

---

### SLIDE 19: CÁC LỚP PHÒNG THỦ ĐÃ TRIỂN KHAI
* **Chống xem trộm điểm (A01):** Máy chủ tự nhận diện người dùng qua phiên làm việc an toàn, tuyệt đối không tin số người dùng gõ trên link.
* **Bảo vệ thư viện mượn ngoài (A03):** Ghim mã băm kiểm tra (SRI); nếu file trên mạng bị kẻ xấu sửa dù 1 ký tự là trình duyệt chặn ngay.
* **Chống dò mật khẩu (A07):** Giới hạn tối đa 5 lần thử sai; đổi mật khẩu là hủy ngay mọi phiên đăng nhập cũ.
* **Xử lý sự cố an toàn (A10):** Khi gặp lỗi thì luôn đóng cửa từ chối; chỉ hiện thông báo lịch sự, giữ kín mã nguồn bên trong.
> 🎙️ **Lời nói:** *"Mỗi lỗ hổng đều có một chốt chặn tương ứng: Không tin dữ liệu người dùng gửi, kiểm tra mã băm thư viện, khóa khi nhập sai nhiều lần, và luôn đóng cửa an toàn khi gặp sự cố."*

---

### SLIDE 20: MINH HỌA A01 — CHỐNG XEM TRỘM ĐIỂM
* **Nguy cơ trước khi vá:**
  * Đường dẫn xem điểm có dạng `?student_id=2`.
  * Sinh viên sửa số `2` thành `3` là đọc được toàn bộ điểm và số CCCD của người khác.
* **Cách khắc phục triệt để:**
  * Bỏ hoàn toàn tham số trên link.
  * Máy chủ luôn tự lấy mã sinh viên từ phiên đăng nhập bí mật `session['user_id']`.
* **Kết quả:** Sinh viên có cố tình gõ số nào trên link thì màn hình vẫn chỉ hiện đúng điểm của chính mình.
> 🎙️ **Lời nói:** *"Cách khắc phục A01 rất đơn giản nhưng hiệu quả: Bỏ tham số trên link và để máy chủ tự quyết định danh tính người dùng dựa trên phiên đăng nhập."*

---

### SLIDE 21: MINH HỌA A03 — CHỐNG ĐẦU ĐỘC THƯ VIỆN
* **Nguy cơ chuỗi cung ứng:**
  * Web dùng thư viện SweetAlert2 từ mạng để làm hộp thông báo đẹp.
  * Nếu máy chủ chứa thư viện đó bị hacker tấn công, chúng có thể chèn mã độc để đánh cắp mật khẩu lúc sinh viên đăng nhập.
* **Cách phòng thủ bằng mã băm (SRI):**
  * Ghim sẵn chuỗi mã băm chuẩn của file vào code trang web.
  * Khi tải về, trình duyệt tự tính mã băm của file: nếu **không khớp** là **lập tức chặn đứng** và không cho chạy.
> 🎙️ **Lời nói:** *"Với thư viện ngoài, nhóm áp dụng cơ chế kiểm tra mã băm. Nếu thư viện bị kẻ gian tráo đổi hoặc sửa dù chỉ một chữ, trình duyệt sẽ phát hiện và tiêu diệt ngay lập tức."*

---

### SLIDE 22: MINH HỌA A07 & A10 — XÁC THỰC & BẮT LỖI
* **Chống dò mật khẩu (A07):**
  * Đặt mức khóa sau 5 lần sai liên tiếp trong 60 giây.
  * Đổi mật khẩu thì toàn bộ thiết bị khác tự động bị đăng xuất.
* **Xử lý sự cố an toàn (A10):**
  * Bắt mọi trường hợp mất mạng hoặc lỗi cơ sở dữ liệu.
  * Trả về thông báo lỗi chung, không in cấu trúc phần mềm ra màn hình.
  * Cơ sở dữ liệu lỗi thì hủy phiên làm việc, không cho ai lợi dụng lách vào.
> 🎙️ **Lời nói:** *"Hệ thống đảm bảo hai nguyên tắc: không để ai dò mật khẩu vô hạn lần, và khi gặp sự cố thì luôn đóng cửa an toàn chứ không mở toang cho kẻ gian lợi dụng."*

---

### SLIDE 23: BẢNG TỔNG HỢP KIỂM THỬ VÀ VÁ LỖI
| Nguy cơ (OWASP 2025) | Lỗ hổng phát hiện | Giải pháp phòng thủ của nhóm | Kết quả kiểm chứng |
| :--- | :--- | :--- | :--- |
| **A01 · Lỗi phân quyền** | Nhận ID sinh viên qua link URL | Danh tính neo chặt vào phiên đăng nhập | Đổi số trên link không lộ điểm |
| **A01 · Vượt quyền GV** | Giảng viên sửa điểm lớp khác | Kiểm tra quyền sở hữu lớp ở từng request | Báo lỗi cấm quyền 403 Forbidden |
| **A03 · Thư viện mạng** | File trên mạng bị sửa đổi | Ghim mã băm toàn vẹn (SRI) | Trình duyệt tự động chặn file bị sửa |
| **A07 · Dò mật khẩu** | Cho thử mật khẩu vô hạn | Khóa IP và tài khoản sau 5 lần sai | Khóa đúng lần 5 trong 60 giây |
| **A10 · Lộ lỗi hệ thống** | In thông báo lỗi kỹ thuật ra web | Bắt ngoại lệ, trả thông báo chung | Bơm 23 dữ liệu lạ, 0 lỗi sập máy |
> 🎙️ **Lời nói:** *"Bảng này tóm gọn toàn bộ kết quả của nhóm: Mỗi nguy cơ đều được kiểm thử thực tế và có giải pháp phòng thủ triệt để từ gốc."*

---

### SLIDE 24: KẾT QUẢ ĐẠT ĐƯỢC & BÀI HỌC
* **Kết quả:**
  * Xây dựng thành công web quản lý đào tạo chạy thực tế.
  * Kiểm thử, khai thác thật và phòng thủ triệt để 4 nhóm OWASP 2025.
  * Dữ liệu nhạy cảm (CCCD) được mã hóa AES-256; lịch sử sửa điểm được lưu vết rõ ràng.
* **Bài học cốt lõi:**
  * **Không tin bất kỳ dữ liệu nào người dùng gửi lên:** Mọi thông tin đều phải được kiểm tra lại ở máy chủ.
  * **Bảo mật là một quá trình liên tục:** Phải viết các bài test tự động để đảm bảo sau này sửa code không bị hổng lại.
* **Hạn chế:** Thử nghiệm trong phạm vi máy tính cá nhân, cần kiểm tra thêm ở quy mô trường học lớn.
> 🎙️ **Lời nói:** *"Bài học lớn nhất nhóm rút ra là: Bảo mật phải được tính toán ngay từ lúc thiết kế hệ thống, không thể viết xong web rồi mới đi chắp vá."*

---

### SLIDE 25: LỜI CẢM ƠN & PHẢN BIỆN
* **Trân trọng cảm ơn Thầy Đỗ Xuân Chợ và Hội đồng!**
* Nhóm 7 (D24) sẵn sàng lắng nghe nhận xét và trả lời các câu hỏi phản biện.
> 🎙️ **Lời nói:** *"Trên đây là toàn bộ phần trình bày của nhóm. Chúng em xin chân thành cảm ơn Thầy và các bạn đã lắng nghe. Nhóm rất mong nhận được những góp ý quý báu từ Thầy!"*
