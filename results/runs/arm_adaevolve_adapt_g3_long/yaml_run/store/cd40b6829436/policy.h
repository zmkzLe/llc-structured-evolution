#ifndef REPLACEMENT_@MODULE@_H
#define REPLACEMENT_@MODULE@_H

#include <cstdint>
#include <vector>

#include "cache.h"
#include "modules.h"

class @MODULE@ : public champsim::modules::replacement
{
private:
  // Constants from the YAML description
  const uint64_t RDP_MAX = 95;
  const int ETR_WIDTH = 5;
  const int ETR_MAX_ABS = 11;
  const int RDP_ENTRIES = 2048;
  const int PC_SIG_BITS = 11;

  // State
  std::vector<int8_t> etr;

  // RDP Table
  struct rdp_entry_t {
    uint8_t value = 0;
    bool valid = false;
  };
  std::vector<rdp_entry_t> rdp;

  // Helper methods
  uint64_t murmur_hash(uint64_t val) const;
  uint64_t get_pc_sig(champsim::address ip, bool hit, access_type type) const;

  rdp_entry_t rdp_read(uint64_t index) const;

public:
  long NUM_SET;
  long NUM_WAY;

  explicit @MODULE@(CACHE* cache);

  long find_victim(uint32_t triggering_cpu, uint64_t instr_id, long set, const champsim::cache_block* current_set, champsim::address ip,
                   champsim::address full_addr, access_type type);
  void update_replacement_state(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr,
                                access_type type, uint8_t hit);
  void replacement_cache_fill(uint32_t triggering_cpu, long set, long way, champsim::address full_addr, champsim::address ip, champsim::address victim_addr,
                              access_type type);
};

#endif
