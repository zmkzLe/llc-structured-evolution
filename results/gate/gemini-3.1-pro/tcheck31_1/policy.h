#ifndef REPLACEMENT_@MODULE@_H
#define REPLACEMENT_@MODULE@_H

#include "cache.h"
#include "modules.h"
#include <vector>
#include <cstdint>

class @MODULE@ : public champsim::modules::replacement {
    long NUM_SET;
    long NUM_WAY;

    struct rdp_entry {
        bool valid = false;
        uint8_t value = 0;
    };
    std::vector<rdp_entry> rdp;

    struct sampler_entry {
        bool valid = false;
        uint16_t tag = 0;
        uint16_t signature = 0;
        uint8_t timestamp = 0;
    };
    std::vector<std::vector<sampler_entry>> sampled_cache;
    std::vector<int> sampled_set_to_group;

    std::vector<int32_t> etr;
    std::vector<uint8_t> etr_clock;
    std::vector<uint8_t> set_clock;

    int32_t wrap_signed_5(int32_t v);
    uint64_t get_pc_sig(champsim::address ip, bool hit, bool prefetch);
    void train_rdp_toward(uint64_t index, uint32_t sample, uint32_t scale, uint32_t min_diff);
    void train_rdp_increment(uint64_t index);
    void run_sampler(uint32_t triggering_cpu, long set, champsim::address full_addr, champsim::address ip, access_type type, bool hit);
    void run_access(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, access_type type, bool hit);

public:
    explicit @MODULE@(CACHE* cache);
    long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip, champsim::address full_addr, access_type type);
    void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr, access_type type, uint8_t hit);
    void replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr, access_type type);
};

#endif
