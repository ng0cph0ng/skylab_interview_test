#include <iostream>
#include <string>
#include <fstream>
#include <thread>
#include <chrono>
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <filesystem>
using namespace std::filesystem;

#ifdef _WIN32
#include <winsock2.h>
#else
#include <arpa/inet.h>
#include <unistd.h>
#endif

using namespace std;

void initSSL()
{
    SSL_library_init();
    SSL_load_error_strings();
    OpenSSL_add_all_algorithms();
}

int main(int argc, char *argv[])
{

    if (argc < 9)
    {
        cout << "Usage:\nclient --client_id <id> --password <pass> --server_host <ip> --server_port <port>\n";
        return 1;
    }

    string cid = argv[2], pwd = argv[4], host = argv[6];
    int port = stoi(argv[8]);

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in server{};
    server.sin_family = AF_INET;
    server.sin_port = htons(port);
    inet_pton(AF_INET, host.c_str(), &server.sin_addr);
    connect(sock, (sockaddr *)&server, sizeof(server));

    initSSL();
    SSL_CTX *ctx = SSL_CTX_new(TLS_client_method());
    SSL *ssl = SSL_new(ctx);
    SSL_set_fd(ssl, sock);
    SSL_connect(ssl);

    string login = "LOGIN " + cid + " " + pwd + "\n";
    SSL_write(ssl, login.c_str(), login.size());

    char buf[4096];
    int len = SSL_read(ssl, buf, sizeof(buf));
    cout << "[SERVER] " << string(buf, len) << endl;

    if (string(buf, len).find("AUTHORIZED") == string::npos)
    {
        cout << "❌ Login failed!\n";
        return 1;
    }

    cout << "Client logged in as: " << cid << endl;

    bool pauseHeartbeat = false;

    thread([&]()
           {
    while(true){
        if(!pauseHeartbeat){
            string ping = "PING\n";
            SSL_write(ssl, ping.c_str(), ping.size());
        }
        this_thread::sleep_for(chrono::seconds(3));
    } })
        .detach();

    // ===== MAIN LOOP =====
    while (true)
    {
        memset(buf, 0, sizeof(buf));
        len = SSL_read(ssl, buf, sizeof(buf));
        if (len <= 0)
            break;

        string msg = string(buf, len);
        cout << "\n[SERVER] " << msg << endl;

        if (msg.find("Enter file path") != string::npos)
        {
            pauseHeartbeat = true;
            cout << "📄 Enter local path: ";
            string path;
            getline(cin, path);

            if (path == "cancel")
            {
                SSL_write(ssl, "cancel\n", 7);
                pauseHeartbeat = false;
                continue;
            }

            ifstream file(path, ios::binary | ios::ate);
            if (!file)
            {
                cout << "❌ File not found.\n";
                continue;
            }

            long size = file.tellg();
            file.seekg(0, ios::beg);

            SSL_write(ssl, (path + "\n").c_str(), path.size() + 1);

            memset(buf, 0, sizeof(buf));
            SSL_read(ssl, buf, sizeof(buf));

            if (string(buf).find("OK START_UPLOAD") == string::npos)
            {
                cout << "❌ Server rejected upload.\n";
                continue;
            }

            string s = to_string(size) + "\n";
            SSL_write(ssl, s.c_str(), s.size());

            char chunk[4096];
            long sent = 0;
            while (file.read(chunk, 4096) || file.gcount() > 0)
            {
                int n = file.gcount();
                SSL_write(ssl, chunk, n);
                sent += n;
                cout << "\r⏳ Uploading... " << (sent * 100 / size) << "%";
                cout.flush();
            }
            cout << "\n✔ Upload done.\n";
            pauseHeartbeat = false;
            continue;
        }

        // Server yêu cầu path lưu file
        // Server yêu cầu path lưu file (download)
        // Server yêu cầu path lưu file (download)
        // Server yêu cầu path lưu file (download)
        if (msg.find("Enter save path") != string::npos)
        {
            pauseHeartbeat = true;
            cout << "📥 Enter save path (folder or full file path): ";
            string save;
            getline(cin, save);

            if (save == "cancel")
            {
                SSL_write(ssl, "cancel\n", 7);
                pauseHeartbeat = false;
                continue;
            }

            // Gửi path sang server
            SSL_write(ssl, (save + "\n").c_str(), save.size() + 1);

            // --- NHẬN metadata: "size|filename"
            memset(buf, 0, sizeof(buf));
            SSL_read(ssl, buf, sizeof(buf));

            string meta = string(buf);
            long size = stol(meta.substr(0, meta.find("|"))); // file size
            string fname = meta.substr(meta.find("|") + 1);   // file name thực sự
            cout << "📦 Server send file: " << fname << " (" << size << " bytes)\n";

            // --- Nếu user nhập thư mục -> ghép tên file
            if (is_directory(save))
            {
                char slash =
#ifdef _WIN32
                    '\\';
#else
                    '/';
#endif

                if (save.back() != slash)
                    save += slash;

                save += fname; // 👈 dùng tên file thật
            }

            cout << "📄 Saving to: " << save << endl;

            // --- Nhận file
            long received = 0;
            ofstream out(save, ios::binary);

            while (received < size)
            {
                int n = SSL_read(ssl, buf, sizeof(buf));
                out.write(buf, n);
                received += n;
                cout << "\r⬇ Downloading... " << (received * 100 / size) << "%";
                cout.flush();
            }

            out.close();
            cout << "\n✔ Download completed\n";

            pauseHeartbeat = false;
            continue;
        }
    }

    SSL_shutdown(ssl);
    SSL_free(ssl);
    SSL_CTX_free(ctx);
    close(sock);
}
