#include <chrono>

using milliseconds = const std::chrono::duration<uint32_t, std::milli>;
using namespace std::chrono_literals;

namespace os
{

milliseconds GetTimeStamp();

void Sleep(milliseconds delay);

} // namespace os
