#include <ios>
#include <iostream>
#include <fstream>
#include <cstring>
#include <string>
#include <list>
#include <unordered_map>
#define BLOCK_SIZE 4096
#define M 58
#define L 48

struct Value {
    char emoji[8];
    char hanzi[8];
    int index;
    Value() { emoji[0]=0; hanzi[0]=0; index=0; }
    bool operator==(const Value& other) const {
        return strcmp(emoji, other.emoji) == 0 && strcmp(hanzi, other.hanzi) == 0 && index == other.index;
    }
    bool operator<(const Value& other) const {
        int cmp = strcmp(emoji, other.emoji);
        if (cmp != 0) return cmp < 0;
        cmp = strcmp(hanzi, other.hanzi);
        if (cmp != 0) return cmp < 0;
        return index < other.index;
    }
};

template <class PageType>
class LRUCache {
private:
    struct Node {
        unsigned int page_id;
        PageType page;
        Node(unsigned int id, const PageType &p) : page_id(id), page(p) {}
    };
    std::list<Node> cache_list;
    std::unordered_map<unsigned int, typename std::list<Node>::iterator> map;
    size_t capacity;

public:
    LRUCache(size_t cap) : capacity(cap) {}

    // 获取页面，若在缓存中则返回true并更新LRU顺序
    bool get(unsigned int page_id, PageType &out) {
        auto it = map.find(page_id);
        if(it == map.end()) return false;
        cache_list.splice(cache_list.begin(), cache_list, it->second);
        out = it->second->page;
        return true;
    }

    // 放置页面，若已存在则更新，否则新插入
    void put(unsigned int page_id, const PageType &p) {
        auto it = map.find(page_id);
        if(it != map.end()) {
            it->second->page = p;
            cache_list.splice(cache_list.begin(), cache_list, it->second);
            return;
        }
        if(cache_list.size() == capacity) { 
            auto &back = cache_list.back();
            map.erase(back.page_id);
            cache_list.pop_back();
        }
        cache_list.push_front(Node(page_id, p));
        map[page_id] = cache_list.begin();
    }
};


template <class T>
void sort(T* l, T* r){
    if(r - l <= 1) return;
    T* i = l;
    T* j = r - 1;
    T pivot = *(l + (r - l) / 2);
    while(i <= j){
        while(*i < pivot) i++;
        while(pivot < *j) j--;
        if(i <= j){
            std::swap(*i, *j);
            i++, j--;
        }
    }
    sort(l, j + 1);
    sort(i, r);
}

template<class T, int info_len = 3>
class MemoryRiver {
private:
    std::fstream file;
    std::string file_name;
    int sizeofT = sizeof(T);
    int HEADER_SIZE = 2 * sizeof(unsigned int);
    unsigned int root_page = 0;
    unsigned int free_list_head = 0;

public:
    MemoryRiver() = default;

    MemoryRiver(const std::string& file_name) : file_name(file_name) {
        file.open(file_name, std::ios::binary | std::ios::in | std::ios::out);
        if (!file) {
            file.clear();
            file.open(file_name, std::ios::binary | std::ios::out);
            file.close();
            file.open(file_name, std::ios::binary | std::ios::in | std::ios::out);
            initialize();
        } else {
            file.seekg(0);
            file.read(reinterpret_cast<char*>(&free_list_head), sizeof(unsigned int));
        }
    }

    ~MemoryRiver() {
        if (file.is_open()) {
            file.close();
        }
    }

    void open_file(){
        if (!file.is_open()) {
            file.open(file_name, std::ios::binary | std::ios::in | std::ios::out);
        }
    }

    void initialize() {
        open_file();
        root_page = 0;
        free_list_head = 0;
        file.seekp(0);
        file.write(reinterpret_cast<const char*>(&root_page), sizeof(unsigned int));
        file.write(reinterpret_cast<const char*>(&free_list_head), sizeof(unsigned int));
    }

    void write_info(unsigned int tmp, int index) {
        open_file();
        file.seekp((index - 1) * sizeof(unsigned int));
        file.write(reinterpret_cast<const char*>(&tmp), sizeof(unsigned int));
    }

    void get_info(unsigned int& tmp, int index) {
        open_file();
        file.seekg((index - 1) * sizeof(unsigned int));
        file.read(reinterpret_cast<char*>(&tmp), sizeof(unsigned int));
    }

    int write_page(T& t) {
        open_file();
        unsigned int page_num;
        get_info(free_list_head, 2);
        if (free_list_head != 0) {
            // Reuse free page
            page_num = free_list_head;
            unsigned int next_free_page;
            file.seekg(HEADER_SIZE + (page_num - 1) * BLOCK_SIZE);
            file.read(reinterpret_cast<char*>(&next_free_page), sizeof(unsigned int));

            // Update file header
            free_list_head = next_free_page;
            write_info(free_list_head, 2);
        } else {
            // Append new page
            file.seekp(0, std::ios::end);
            page_num = (static_cast<std::streamoff>(file.tellp()) - HEADER_SIZE) / BLOCK_SIZE + 1;
        }

        char buffer[BLOCK_SIZE] = {0};
        memcpy(buffer, &t, sizeofT);

        file.seekp(HEADER_SIZE + (page_num - 1) * BLOCK_SIZE);
        file.write(buffer, BLOCK_SIZE);

        return page_num;
    }

    void delete_page(int page_num) {
        open_file();
        get_info(free_list_head, 2);
        file.seekp(HEADER_SIZE + (page_num - 1) * BLOCK_SIZE);
        file.write(reinterpret_cast<char*>(&free_list_head), sizeof(unsigned int));

        // Update file header
        free_list_head = page_num;
        write_info(free_list_head, 2);
    }

    void read_page(T& t, int page_num) {
        open_file();
        char buffer[BLOCK_SIZE] = {0};
        file.seekg(HEADER_SIZE + (page_num - 1) * BLOCK_SIZE);
        file.read(buffer, BLOCK_SIZE);
        memcpy(&t, buffer, sizeofT);
    }

    void update_page(T& t, int page_num) {
        open_file();
        char buffer[BLOCK_SIZE] = {0};
        memcpy(buffer, &t, sizeofT);
        file.seekp(HEADER_SIZE + (page_num - 1) * BLOCK_SIZE);
        file.write(buffer, BLOCK_SIZE);
    }
};

#pragma pack(push, 1)
template<class Key, class Value>
struct BPTNode {
    bool is_leaf;
    int count;
    unsigned int parent;
    unsigned int next_leaf;

    struct LeafEntry {
        Key index;
        Value value;
    };
    struct InternalEntry {
        Key index;
        unsigned int child;
    };

    union {
        LeafEntry leaf_entries[(BLOCK_SIZE - sizeof(bool) - sizeof(int) - 2 * sizeof(unsigned int)) / sizeof(LeafEntry)];
        InternalEntry internal_entries[(BLOCK_SIZE - sizeof(bool) - sizeof(int) - 2 * sizeof(unsigned int)) / sizeof(InternalEntry)];
    };

    BPTNode() : is_leaf(false), count(0), parent(0), next_leaf(0) {
        memset(&leaf_entries, 0, sizeof(leaf_entries));
    }
};
#pragma pack(pop)

static_assert(sizeof(BPTNode<char[64], int>) <= BLOCK_SIZE, "BPTNode size exceeds BLOCK_SIZE!");

template<class Key, class Value>
class BPT {
private:
    MemoryRiver<BPTNode<Key, Value>> file;
    unsigned int root_page = 0;
    
    // 创建一个LRU缓存，容量可根据需求调整
    LRUCache<BPTNode<Key, Value>> cache;

    void disk_read(BPTNode<Key, Value> &node, unsigned int page) {
        // 优先从LRU缓存中取
        if(!cache.get(page, node)) {
            file.read_page(node, page);
            cache.put(page, node);
        }
    }

    void disk_write(BPTNode<Key, Value> &node, unsigned int page) {
        file.update_page(node, page);
        cache.put(page, node); // 写入后更新缓存
    }

    void disk_delete(unsigned int page) {
        file.delete_page(page);
        // 若需要可补充清理缓存逻辑，如:
        // // cache.evict(page);
    }

    unsigned int disk_alloc(BPTNode<Key, Value> &node) {
        unsigned int pg = file.write_page(node);
        cache.put(pg, node);
        return pg;
    }

public:
    BPT(const std::string& filename) : file(filename), cache(128) {
        file.get_info(root_page, 1);
        if (root_page == 0) {
            initialize_new_tree();
        }
    }

    void initialize_new_tree() {
        // 1. Create a new leaf node
        BPTNode<Key, Value> leaf_node; // parent later be overwritten
        leaf_node.is_leaf = true;
        leaf_node.count = 0;
        leaf_node.next_leaf = 0;
        unsigned int leaf_page = disk_alloc(leaf_node);
        
        // 2. Create a new root node (internal node, pointing to the leaf)
        BPTNode<Key, Value> root_node;
        root_node.is_leaf = false;
        root_node.count = 1;
        root_node.parent = 0;
        root_node.next_leaf = 0;
        root_node.internal_entries[0].child = leaf_page;
        memset(root_node.internal_entries[0].index, 0, 64);
        root_page = disk_alloc(root_node);

        // 3. Update the parent of the leaf node
        leaf_node.parent = root_page;
        disk_write(leaf_node, leaf_page);

        file.write_info(root_page, 1);
        file.write_info(0, 2); // free_list_head
        disk_read(leaf_node, leaf_page);
    }

    void insert(const Key& index, Value value, BPTNode<Key, Value> *now_node, int now_page) {
        if (now_node->is_leaf == true){
            int j = now_node->count - 1;
            for (; j >= 0; --j) {
                if (memcmp(index, now_node->leaf_entries[j].index, 64) >= 0) {
                    break;
                }
                now_node->leaf_entries[j + 1] = now_node->leaf_entries[j];
            }
            memcpy(now_node->leaf_entries[j + 1].index, index, 64);
            now_node->leaf_entries[j + 1].value = value;
            now_node->count++;
            disk_write(*now_node, now_page);
            return;
        }
        int left = 0, right = now_node->count - 1, i = 0;
        while (left <= right) {
            int mid = (left + right) >> 1;
            if (memcmp(index, now_node->internal_entries[mid].index, 64) >= 0) {
                i = mid;
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }
        unsigned int child_page = now_node->internal_entries[i].child;
        BPTNode<Key, Value> child_node;
        disk_read(child_node, child_page);
        insert(index, value, &child_node, child_page);

        // Check if the child node is full
        int limit = (child_node.is_leaf ? L : M);
        if (child_node.count >= limit) {
            // Split the child node
            BPTNode<Key, Value> new_child_node;
            new_child_node.is_leaf = child_node.is_leaf;
            new_child_node.count = 0;
            new_child_node.parent = child_node.parent;
            new_child_node.next_leaf = child_node.next_leaf;

            // Move half of the entries to the new child node
            for (int j = limit / 2; j < child_node.count; ++j) {
                if (child_node.is_leaf) {
                    new_child_node.leaf_entries[new_child_node.count++] = child_node.leaf_entries[j];
                } else {
                    new_child_node.internal_entries[new_child_node.count++] = child_node.internal_entries[j];
                }
            }
            unsigned int new_child_page = disk_alloc(new_child_node);
            
            child_node.count = limit / 2;
            child_node.next_leaf = new_child_page;
            disk_write(child_node, child_page);

            // Update the parent node
            for (int j = now_node->count - 1; j > i; --j) {
                now_node->internal_entries[j + 1] = now_node->internal_entries[j];
            }
            if (child_node.is_leaf) {
                memcpy(now_node->internal_entries[i + 1].index, new_child_node.leaf_entries[0].index, 64);
            } else {
                memcpy(now_node->internal_entries[i + 1].index, new_child_node.internal_entries[0].index, 64);
            }
            now_node->internal_entries[i + 1].child = new_child_page;
            now_node->count++;
            disk_write(*now_node, now_page);
        }
    }

    bool remove(const Key& index, Value value, BPTNode<Key, Value> *now_node, int now_page) {
        if (now_node->is_leaf) {
            int j = 0;
            for (; j < now_node->count; ++j) {
                if (memcmp(index, now_node->leaf_entries[j].index, 64) == 0 && now_node->leaf_entries[j].value == value) {
                    break;
                }
            }
            if (j == now_node->count) return false; // Not found
            for (int k = j; k < now_node->count - 1; ++k) {
                now_node->leaf_entries[k] = now_node->leaf_entries[k + 1];
            }
            now_node->count--;
            disk_write(*now_node, now_page);
            return true;
        }
        int left = 0, right = now_node->count - 1, i = 0;
        while (left <= right) {
            int mid = (left + right) >> 1;
            if (memcmp(index, now_node->internal_entries[mid].index, 64) > 0) {
                i = mid;
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }
        // Search every child node containing the key
        for (; i < now_node->count && memcmp(index, now_node->internal_entries[i].index, 64) >= 0; ++i) {
            unsigned int child_page = now_node->internal_entries[i].child;
            BPTNode<Key, Value> child_node;
            disk_read(child_node, child_page);
            bool flag = remove(index, value, &child_node, child_page);
            if (!flag) {
                continue;
            }
            if (child_node.count < (child_node.is_leaf ? L : M) / 2 && now_node -> count > 1) {
                // Merge or borrow from sibling
                BPTNode<Key, Value> sibling_node;
                unsigned int sibling_page = 0;
                if (i > 0) {
                    sibling_page = now_node->internal_entries[i - 1].child;
                    disk_read(sibling_node, sibling_page);
                } else {
                    sibling_page = now_node->internal_entries[i + 1].child;
                    disk_read(sibling_node, sibling_page);
                }
                if (sibling_node.count + child_node.count <= (child_node.is_leaf ? L : M)) {
                    // Merge
                    if (i > 0) { // Merge with left sibling
                        if (child_node.is_leaf) {
                            for (int j = 0; j < child_node.count; ++j) {
                                sibling_node.leaf_entries[sibling_node.count++] = child_node.leaf_entries[j];
                            }
                        } else {
                            for (int j = 0; j < child_node.count; ++j) {
                                sibling_node.internal_entries[sibling_node.count++] = child_node.internal_entries[j];
                            }
                        }
                        sibling_node.next_leaf = child_node.next_leaf;
                        disk_write(sibling_node, sibling_page);
                        for (int j = i; j < now_node->count - 1; ++j) {
                            now_node->internal_entries[j] = now_node->internal_entries[j + 1];
                        }
                        now_node->count--;
                        disk_write(*now_node, now_page);
                        disk_delete(child_page);
                    } else { // Merge with right sibling
                        if (child_node.is_leaf) {
                            for (int j = 0; j < sibling_node.count; ++j) {
                                child_node.leaf_entries[child_node.count++] = sibling_node.leaf_entries[j];
                            }
                        } else {
                            for (int j = 0; j < sibling_node.count; ++j) {
                                child_node.internal_entries[child_node.count++] = sibling_node.internal_entries[j];
                            }
                        }
                        disk_write(child_node, child_page);
                        for (int j = i + 1; j < now_node->count - 1; ++j) {
                            now_node->internal_entries[j] = now_node->internal_entries[j + 1];
                        }
                        now_node->count--;
                        disk_write(*now_node, now_page);
                        disk_delete(sibling_page);
                    }
                } else {
                    if (child_node.is_leaf) {
                        if (i > 0) {
                            for (int j = child_node.count - 1; j >= 0; --j) {
                                child_node.leaf_entries[j + 1] = child_node.leaf_entries[j];
                            }
                            child_node.leaf_entries[0] = sibling_node.leaf_entries[sibling_node.count - 1];
                            child_node.count++;
                            sibling_node.count--;
                            memcpy(now_node->internal_entries[i].index, child_node.leaf_entries[0].index, 64);
                        }
                        else {
                            child_node.leaf_entries[child_node.count++] = sibling_node.leaf_entries[0];
                            for (int j = 1; j < sibling_node.count; ++j) {
                                sibling_node.leaf_entries[j - 1] = sibling_node.leaf_entries[j];
                            }
                            sibling_node.count--;
                            memcpy(now_node->internal_entries[i + 1].index, sibling_node.leaf_entries[0].index, 64);
                        }
                        disk_write(child_node, child_page);
                        disk_write(sibling_node, sibling_page);
                        disk_write(*now_node, now_page);
                    } else {
                        if (i > 0) {
                            for (int j = child_node.count - 1; j >= 0; --j) {
                                child_node.internal_entries[j + 1] = child_node.internal_entries[j];
                            }
                            child_node.internal_entries[0] = sibling_node.internal_entries[sibling_node.count - 1];
                            child_node.count++;
                            sibling_node.count--;
                            memcpy(now_node->internal_entries[i].index, child_node.internal_entries[0].index, 64);
                        } else {
                            child_node.internal_entries[child_node.count++] = sibling_node.internal_entries[0];
                            for (int j = 1; j < sibling_node.count; ++j) {
                                sibling_node.internal_entries[j - 1] = sibling_node.internal_entries[j];
                            }
                            sibling_node.count--;
                            memcpy(now_node->internal_entries[i + 1].index, sibling_node.internal_entries[0].index, 64);
                        }
                        disk_write(child_node, child_page);
                        disk_write(sibling_node, sibling_page);
                        disk_write(*now_node, now_page);
                    }
                }
            }
            return true;
        }
        return false;
    }

    void find_all(const Key& index, Value* values, int& count, BPTNode<Key, Value> *now_node) {
        if (now_node->count == 0) return;
        if (now_node->is_leaf) {
            for (int i = 0; i < now_node->count; ++i) {
                if (memcmp(index, now_node->leaf_entries[i].index, 64) == 0) {
                    values[count++] = now_node->leaf_entries[i].value;
                }
            }
            return;
        }
        int left = 0, right = now_node->count - 1, i = 0;
        while (left <= right) {
            int mid = (left + right) >> 1;
            if (memcmp(index, now_node->internal_entries[mid].index, 64) > 0) {
                i = mid;
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }
        // E.g. index = "35", now_node->internal_entries[i].index = "35", start searching from i - 1
        while (i < now_node->count && memcmp(index, now_node->internal_entries[i].index, 64) >= 0) {
            unsigned int child_page = now_node->internal_entries[i].child;
            BPTNode<Key, Value> child_node;
            disk_read(child_node, child_page);
            find_all(index, values, count, &child_node);
            ++i;
        } // To solve the issue that different values may reside in different blocks
    }

    void insert(const Key& index, Value value) {
        BPTNode<Key, Value> root_node;
        disk_read(root_node, root_page);
        insert(index, value, &root_node, root_page);

        // Grow up the tree if necessary
        if (root_node.count >= M) {
            BPTNode<Key, Value> new_root_node;
            new_root_node.is_leaf = false;
            new_root_node.count = 2;
            new_root_node.parent = 0;
            new_root_node.next_leaf = 0;
            BPTNode<Key, Value> new_child_node;
            new_child_node.is_leaf = false;
            new_child_node.count = 0;
            new_child_node.parent = 0;
            new_child_node.next_leaf = 0;
            unsigned int new_child_page = disk_alloc(new_child_node);

            // Move half of the entries to the new child node
            for (int j = M / 2; j < root_node.count; ++j) {
                new_child_node.internal_entries[new_child_node.count++] = root_node.internal_entries[j];
                root_node.internal_entries[j].index[0] = '\0';
            }
            root_node.count = M / 2;
            
            // Update the parent node
            new_root_node.internal_entries[0].child = root_page;
            memcpy(new_root_node.internal_entries[0].index, root_node.internal_entries[0].index, 64);
            new_root_node.internal_entries[1].child = new_child_page;
            memcpy(new_root_node.internal_entries[1].index, new_child_node.internal_entries[0].index, 64);

            unsigned int old_root_page = root_page;
            root_page = disk_alloc(new_root_node);
            // root_page changed
            
            root_node.parent = root_page;
            root_node.next_leaf = new_child_page;
            disk_write(root_node, old_root_page);

            new_child_node.parent = root_page;
            disk_write(new_child_node, new_child_page);
            
            file.write_info(root_page, 1);
        }
    }

    void remove(const Key& index, Value value) {
        BPTNode<Key, Value> root_node;
        disk_read(root_node, root_page);
        remove(index, value, &root_node, root_page);

        // Shrink the tree if necessary
        if (root_node.count == 1) {
            BPTNode<Key, Value> child_node;
            disk_read(child_node, root_node.internal_entries[0].child);
            if (child_node.is_leaf) {
                return;
            } else {
                disk_delete(root_page);
                root_page = root_node.internal_entries[0].child;
                file.write_info(root_page, 1);
            }
        }
    }

    void find(const Key& index, Value* values, int& count) {
        BPTNode<Key, Value> root_node;
        disk_read(root_node, root_page);
        find_all(index, values, count, &root_node);
    }

    void print(const BPTNode<Key, Value>& node, int now_page) {
        std::cout << "Page: " << now_page << ", Count: " << node.count << ", Is Leaf: " << node.is_leaf << std::endl;
        if (node.is_leaf) {
            for (int i = 0; i < node.count; ++i) {
                std::cout << node.leaf_entries[i].index << " " << node.leaf_entries[i].value << std::endl;
            }
        } else {
            for (int i = 0; i < node.count; ++i) {
                std::cout << node.internal_entries[i].index << " ";
                std::cout << std::endl;
            }
            for (int i = 0; i < node.count; ++i) {
                BPTNode<Key, Value> child_node;
                disk_read(child_node, node.internal_entries[i].child);
                print(child_node, node.internal_entries[i].child);
            }
        }
    }

    void print_all() {
        BPTNode<Key, Value> root_node;
        disk_read(root_node, root_page);
        print(root_node, root_page);
        std::cout << "------------------------" << std::endl;
    }
    
};

int main() {
    freopen("query_data.in", "r", stdin);
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    std::cout.tie(nullptr);
    BPT<char[64], Value> tree("dataset.db");
    int n;
    std::cin >> n;
    while (n--) {
        std::string cmd, index, emoji, hanzi;
        int idx;
        std::cin >> cmd;
        if (cmd == "insert") {
            std::cin >> index >> emoji >> hanzi >> idx;
            char index_buf[64] = {0};
            strncpy(index_buf, index.c_str(), 64);
            Value v;
            strncpy(v.emoji, emoji.c_str(), 8);
            strncpy(v.hanzi, hanzi.c_str(), 8);
            v.index = idx;
            tree.insert(index_buf, v);
        } else if (cmd == "find") {
            std::cin >> index;
            char index_buf[64] = {0};
            strncpy(index_buf, index.c_str(), 64);
            Value values[300000];
            int count = 0;
            tree.find(index_buf, values, count);
            sort(values, values + count);
            for (int i = 0; i < count; ++i) {
                std::cout << values[i].emoji << " " << values[i].hanzi << " " << values[i].index << std::endl;
            }
            if (count == 0) {
                std::cout << "null";
            }
            std::cout << std::endl;
        } else if (cmd == "delete") {
            std::cin >> index >> emoji >> hanzi >> idx;
            char index_buf[64] = {0};
            strncpy(index_buf, index.c_str(), 64);
            Value v;
            strncpy(v.emoji, emoji.c_str(), 8);
            strncpy(v.hanzi, hanzi.c_str(), 8);
            v.index = idx;
            tree.remove(index_buf, v);
        }
        // tree.print_all();
    }
    return 0;
}