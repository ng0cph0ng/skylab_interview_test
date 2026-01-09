#include <iostream>
#include <string>
#include <fstream>
#include <thread>
#include <chrono>
#include <filesystem>
#include <atomic>
#include <openssl/ssl.h>
#include <openssl/err.h>
#include <openssl/sha.h>

using namespace std;
namespace fs = std::filesystem;

#ifdef _WIN32
#define _WINSOCK_DEPRECATED_NO_WARNINGS
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0600
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <arpa/inet.h>
#include <unistd.h>
#endif

// ========== SSL INIT ==========
void initSSL()
{
    SSL_library_init();
    SSL_load_error_strings();
    OpenSSL_add_all_algorithms();
}

// ========== SHA256 ==========
string sha256file(const string &path)
{
    ifstream f(path, ios::binary);

    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    const EVP_MD *md = EVP_sha256();
    EVP_DigestInit_ex(ctx, md, NULL);

    char buf[4096];
    while (f.read(buf, sizeof(buf)) || f.gcount() > 0)
    {
        EVP_DigestUpdate(ctx, buf, f.gcount());
    }

    unsigned char hash[EVP_MAX_MD_SIZE];
    unsigned int len = 0;
    EVP_DigestFinal_ex(ctx, hash, &len);
    EVP_MD_CTX_free(ctx);

    string hex;
    char tmp[3];
    for (unsigned int i = 0; i < len; i++)
    {
        sprintf(tmp, "%02x", hash[i]);
        hex += tmp;
    }
    return hex;
}

// ========== UNIQUE NAME ==========
string getUniqueFilename(const string &dir, const string &filename)
{
    fs::path basePath(filename);
    string stem = basePath.stem().string();
    string ext = basePath.extension().string();
    int counter = 1;
    fs::path fullPath = fs::path(dir) / filename;

    while (fs::exists(fullPath))
    {
        string newName = stem + " (" + to_string(counter++) + ")" + ext;
        fullPath = fs::path(dir) / newName;
    }
    return fullPath.filename().string();
}

// ========== MAIN ==========
int main(int argc, char *argv[])
{
#ifdef _WIN32
    WSADATA wsa;
    WSAStartup(MAKEWORD(2, 2), &wsa);
#endif

    if (argc < 9)
    {
        cout << "Usage:\nclient --client_id <id> --password <pass> --server_host <ip> --server_port <port>\n";
        return 1;
    }

    string cid = argv[2], pwd = argv[4], host = argv[6];
    int port = stoi(argv[8]);

    // ========== Create socket ==========
    int sock = socket(AF_INET, SOCK_STREAM, 0);

    sockaddr_in server{};
    server.sin_family = AF_INET;
    server.sin_port = htons(port);

#ifdef _WIN32
    inet_pton(AF_INET, host.c_str(), &(server.sin_addr));
#else
    inet_pton(AF_INET, host.c_str(), &server.sin_addr);
#endif

    connect(sock, (sockaddr *)&server, sizeof(server));

    // ========== SSL ==========
    initSSL();
    SSL_CTX *ctx = SSL_CTX_new(TLS_client_method());
    SSL *ssl = SSL_new(ctx);
    SSL_set_fd(ssl, sock);
    SSL_connect(ssl);

    // ========== LOGIN ==========
    string login = "LOGIN " + cid + " " + pwd + "\n";
    SSL_write(ssl, login.c_str(), login.size());

    char buf[4096];
    int len = SSL_read(ssl, buf, sizeof(buf));
    string reply(buf, len);
    cout << reply << endl;
    if (reply.find("AUTHORIZED") == string::npos)
        return 1;

    atomic<bool> transferring(false);
    atomic<bool> terminate(false);

    string lastUploadPath = "";
    string lastChecksum = "";
    string pathfile = "upload_path.txt";

    {
        ifstream p(pathfile);
        if (p)
        {
            getline(p, lastUploadPath);
            getline(p, lastChecksum);
        }
    }

    // ========== HEARTBEAT THREAD ==========
    thread([&]()
           {
        while (!terminate)
        {
            this_thread::sleep_for(chrono::seconds(3));
            if (!transferring)
            {
                string ping = "PING\n";
                SSL_write(ssl, ping.c_str(), ping.size());
            }
        } })
        .detach();

    while (true)
    {
        memset(buf, 0, sizeof(buf));
        len = SSL_read(ssl, buf, sizeof(buf));
        if (len <= 0)
            break;

        string msg(buf, len);
        cout << "\n[SERVER] " << msg << endl;

        // ========== RESUME UPLOAD ==========
        if (msg.rfind("OFFSET", 0) == 0)
        {
            transferring = true;
            long offset = stol(msg.substr(7));

            if (lastUploadPath == "")
            {
                SSL_write(ssl, "cancel\n", 7);
                transferring = false;
                continue;
            }

            ifstream file(lastUploadPath, ios::binary);
            if (!file)
            {
                SSL_write(ssl, "cancel\n", 7);
                transferring = false;
                continue;
            }

            long size = fs::file_size(lastUploadPath);
            file.seekg(offset);

            long sent = offset;
            char chunk[4096];

            while (sent < size)
            {
                long to_send = min((long)sizeof(chunk), size - sent);
                file.read(chunk, to_send);
                streamsize n = file.gcount();
                if (n <= 0)
                    break;

                int sent_now = SSL_write(ssl, chunk, n);
                if (sent_now <= 0)
                {
                    cout << "\n⛔ Upload aborted by server.\n";
                    transferring = false;
                    break;
                }
                sent += n;

                cout << "\r⏳ Resume... " << (sent * 100 / size) << "%";
                cout.flush();
            }

            if (sent == size)
            {
                string msg_ck = "CHECKSUM " + lastChecksum + "\n";
                SSL_write(ssl, msg_ck.c_str(), msg_ck.size());
                cout << "\n✔ Resume completed\n";
            }
            else
            {
                cout << "\n⛔ Resume canceled.\n";
            }

            transferring = false;
            continue;
        }

        // ========== NEW UPLOAD ==========
        if (msg.find("Enter file path") != string::npos)
        {
            transferring = true;

            cout << "📄 Enter local file path: ";
            string path;
            getline(cin, path);

            lastUploadPath = path;

            if (path == "cancel")
            {
                SSL_write(ssl, "cancel\n", 7);
                transferring = false;
                continue;
            }

            ifstream file(path, ios::binary | ios::ate);
            if (!file)
            {
                transferring = false;
                continue;
            }

            long size = file.tellg();
            file.seekg(0);

            lastChecksum = sha256file(path);

            ofstream pf(pathfile);
            pf << lastUploadPath << "\n"
               << lastChecksum;
            pf.close();

            SSL_write(ssl, (path + "\n").c_str(), path.size() + 1);

            memset(buf, 0, sizeof(buf));
            SSL_read(ssl, buf, sizeof(buf));
            if (string(buf).find("OK START_UPLOAD") == string::npos)
            {
                transferring = false;
                continue;
            }

            string s = to_string(size) + "\n";
            SSL_write(ssl, s.c_str(), s.size());

            memset(buf, 0, sizeof(buf));
            SSL_read(ssl, buf, sizeof(buf));
            long skip = stol(string(buf));

            file.seekg(skip);
            long sent = skip;
            char chunk[4096];

            while (sent < size)
            {
                long to_send = min((long)sizeof(chunk), size - sent);
                file.read(chunk, to_send);
                streamsize n = file.gcount();
                if (n <= 0)
                    break;

                int sent_now = SSL_write(ssl, chunk, n);
                if (sent_now <= 0)
                {
                    cout << "\n⛔ Upload aborted by server.\n";
                    transferring = false;
                    break;
                }
                sent += n;

                cout << "\r⏳ Uploading... " << (sent * 100 / size) << "%";
                cout.flush();
            }

            if (sent == size)
            {
                string msg_ck = "CHECKSUM " + lastChecksum + "\n";
                SSL_write(ssl, msg_ck.c_str(), msg_ck.size());
                cout << "\n✔ Upload sent.\n";
            }
            else
            {
                cout << "\n⛔ Upload canceled.\n";
            }

            remove(pathfile.c_str());
            lastUploadPath = "";
            lastChecksum = "";
            transferring = false;
            continue;
        }

        // ========== DOWNLOAD ==========
        if (msg.find("Enter save path") != string::npos)
        {
            transferring = true;

            cout << "📥 Save directory: ";
            string saveDir;
            getline(cin, saveDir);

            if (saveDir == "cancel")
            {
                SSL_write(ssl, "cancel\n", 7);
                transferring = false;
                continue;
            }

            if (!fs::exists(saveDir) || !fs::is_directory(saveDir))
            {
                SSL_write(ssl, "cancel\n", 7);
                transferring = false;
                continue;
            }

            SSL_write(ssl, (saveDir + "\n").c_str(), saveDir.size() + 1);

            memset(buf, 0, sizeof(buf));
            SSL_read(ssl, buf, sizeof(buf));
            string meta(buf);
            long size = stol(meta.substr(0, meta.find("|")));
            string fname = meta.substr(meta.find("|") + 1);
            while (!fname.empty() && (fname.back() == '\n' || fname.back() == '\r'))
                fname.pop_back();

#ifdef _WIN32
            char slash = '\\';
#else
            char slash = '/';
#endif

            if (saveDir.back() != slash)
                saveDir += slash;
            string finalName = getUniqueFilename(saveDir, fname);
            string fullPath = saveDir + finalName;

            ofstream out(fullPath, ios::binary);
            long received = 0;

            while (received < size)
            {
                int n = SSL_read(ssl, buf, sizeof(buf));
                if (n <= 0)
                    break;
                out.write(buf, n);
                received += n;
                cout << "\r⬇ Downloading... " << (received * 100 / size) << "%";
                cout.flush();
            }

            out.close();
            cout << "\n✔ Download completed: " << fullPath << endl;
            transferring = false;
            continue;
        }
    }

    terminate = true;
    SSL_shutdown(ssl);
    SSL_free(ssl);
    SSL_CTX_free(ctx);

#ifdef _WIN32
    closesocket(sock);
    WSACleanup();
#else
    close(sock);
#endif

    return 0;
}
