# ChatBot🧬🤖

Trợ lý ảo AI thông minh phục vụ nội bộ, chuyên hỗ trợ giải đáp thắc mắc về domain chuyên sâu,thông qua công nghệ RAG (Retrieval-Augmented Generation).Được thiết kế linh hoạt để chạy được trên cả CPU và GPU.

## 🌟 Tính năng nổi bật

- **Hỏi đáp thông minh (RAG)**: Truy xuất kiến thức trực tiếp từ các tài liệu (PDF, Docx).
- **Phân tích công thức (MathGuard)**: Tự động nhận diện và tính toán các công thức phức tạp (lương, thuế,...).
- **Giao diện ChatGPT-style**: Trải nghiệm trò chuyện mượt mà, hỗ trợ đa ngôn ngữ (Tiếng Việt, Tiếng Trung, Tiếng Anh).
- **Hủy bỏ yêu cầu tức thì (True Abortion)**: Khả năng dừng tạo câu trả lời ngay lập tức để tiết kiệm tài nguyên.
- **Quản lý hội thoại**: Lưu trữ lịch sử chat, quản lý Thread thông minh.

## 🏗️ Kiến trúc hệ thống

```mermaid
graph TD
    classDef frontend fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff
    classDef backend fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff
    classDef ai fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#fff
    classDef db fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff

    subgraph "Presentation Layer"
        UI["💻 React.js SPA<br/>(TailwindCSS)"]:::frontend
    end

    subgraph "Application Logic Layer"
        API["⚙️ Node.js Gateway<br/>(Express API)"]:::backend
        SOCKET["🔌 Socket.IO TCP<br/>(Realtime Server)"]:::backend
        QUEUE["⏳ BullMQ<br/>(Job Manager)"]:::backend
        WORKER["🛠️ BullMQ Worker"]:::backend
    end

    subgraph "AI / ML Engine Layer"
        FASTAPI["🧠 FastAPI API Gateway"]:::ai
        AGENT["🤖 Orchestrator Agent"]:::ai
        LLM["⚙️ Local LLM (Ollama)"]:::ai
    end

    subgraph "Persistence Layer (Storage / Memory)"
        REDIS[("⚡ Redis<br>(Cache/PubSub/Queue)")]:::db
        SQLITE[("🗄️ SQLite<br/>(Users/Chat History)")]:::db
        CHROMA[("📊 ChromaDB<br/>(Vector Embeddings)")]:::db
    end

    UI <--> API
    UI <--> SOCKET
    API --> QUEUE
    QUEUE <--> REDIS
    QUEUE --> WORKER
    WORKER --> FASTAPI
    FASTAPI --> AGENT
    AGENT --> LLM
    API <--> SQLITE
    AGENT <--> CHROMA
```

### 2. Data Flow Pipeline (End-to-End Execution)
Luồng đi của một câu hỏi từ khi Người dùng gõ đến khi có kết quả Realtime.
```mermaid
graph LR
    classDef step fill:#f8fafc,stroke:#334155,stroke-width:2px,color:#0f172a
    classDef data fill:#fdf4ff,stroke:#c026d6,stroke-width:2px,color:#701a75

    USER((User))
    API["Thêm Job vào Queue"]:::step
    REDIS[("Redis")]:::data
    WORKER["Python nhận Job"]:::step
    ROUTER{"Phân loại Intent"}:::step
    QA["Truy xuất Docs"]:::step
    LLM["Sinh Text (LLM)"]:::step
    SOCKET["Stream Tokens<br>qua Websocket"]:::step

    USER -->|1. Request| API
    API -->|2. Push| REDIS
    REDIS -->|3. Pop| WORKER
    WORKER -->|4. Parse| ROUTER
    
    ROUTER -->|Toán học| LLM
    ROUTER -->|Luật công ty| QA
    
    QA -->|Lấy Vector| LLM
    LLM -->|5. Token by token| SOCKET
    SOCKET -->|6. Render chunk| USER
```

### 3. Workflow của Agent Loop (RAG Logic)
Quy trình ra quyết định của tác tử AI bên trong tầng Python FastAPI.
```mermaid
graph TD
    classDef init fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    classDef decision fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#92400e
    classDef tool fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#166534

    INPUT["Nhận Query từ Node.js"]:::init
    FORMAT["Format lại Query"]:::init
    
    INTENT{"Intent Agent<br/>(Dự đoán mục đích)"}:::decision
    
    TOOL1["MathGuard Agent<br/>(Chạy Python Eval)"]:::tool
    TOOL2["Vector Retriever<br/>(ChromaDB Top-K)"]:::tool
    TOOL3["Direct Conversation<br/>(Chào hỏi/Quy tắc)"]:::tool
    
    DRAFT["Drafting Agent<br/>(Viết nháp dựa trên Context)"]:::init
    VALIDATE{"Validation Agent<br/>(Tránh Hallucination)"}:::decision
    
    OUTPUT["Trả kết quả Cuối"]:::init

    INPUT --> FORMAT
    FORMAT --> INTENT
    
    INTENT -->|Toán/Lương| TOOL1
    INTENT -->|Chính sách| TOOL2
    INTENT -->|Chào hỏi| TOOL3
    
    TOOL1 --> DRAFT
    TOOL2 --> DRAFT
    TOOL3 --> DRAFT
    
    DRAFT --> VALIDATE
    
    VALIDATE -->|Fail: Sai lệch| INTENT
    VALIDATE -->|Pass: An toàn| OUTPUT
```

1.  **Frontend (React + Vite + Tailwind)**: Giao diện người dùng hiện đại, responsive.
2.  **Backend (Node.js + Express + BullMQ)**: Xử lý logic nghiệp vụ, quản lý hàng chờ (Job Queue) và kết nối Socket.IO truyền dữ liệu realtime.
3.  **RAG Service (Python + FastAPI)**: "Bộ não" AI xử lý ngôn ngữ tự nhiên, truy xuất tài liệu và chạy mô hình LLM.
4.  **Database**:
    *   **SQLite**: Lưu trữ user, thread và tin nhắn.
    *   **Redis**: Backing store cho hàng chờ công việc BullMQ.
    *   **ChromaDB**: Cơ sở dữ liệu vector để lưu trữ và truy xuất tài liệu nội bộ một cách nhanh chóng.

## 🚀 Hướng dẫn cài đặt

### 1. Yêu cầu hệ thống
- Node.js v18+
- Python 3.10+
- Redis Server
- Ollama (để chạy LLM local)

### 2. Cài đặt các thành phần

#### RAG Service (Python)
```bash
cd rag-service
python -m venv venv
source venv/bin/activate  # Hoặc venv\Scripts\activate trên Windows
pip install -r requirements.txt
```

#### Backend (Node.js)
```bash
cd backend
npm install
```

#### Frontend (React)
```bash
cd frontend
npm install
```

### 3. Cấu hình
- Tạo file `.env` trong thư mục `backend` dựa trên các biến môi trường cần thiết (PORT, REDIS_URL, RAG_SERVICE_URL).
- Đảm bảo Ollama đang chạy và đã pull model (mặc định là `qwen2.5:7b` hoặc tương đương).
-Thêm các file data có dạng docx,pdf,txt... vào thư mục ./rag-service/data để vector embedding data.

### 4. Khởi chạy
- **Python**: `python -m src.api.server` (trong thư mục `rag-service`)
- **Backend**: `npm start` (trong thư mục `backend`)
- **Frontend**: `npm run dev` (trong thư mục `frontend`)

## 🛡️ Bảo mật & Hiệu năng
- Hệ thống hỗ trợ dừng xử lý ngầm khi client ngắt kết nối.
- Cơ chế Sequential Worker đảm bảo ổn định tài nguyên hệ thống.
- MathGuard đảm bảo tính chính xác cho các phép tính kỹ thuật.

---
© 2imyuH.
