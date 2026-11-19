// CDC console: status, codec registers, TDM checks, output test signals.
#ifndef CONSOLE_H_
#define CONSOLE_H_

void console_task(void);
// printf to the console (dropped when the CDC FIFO is full).
void console_printf(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#endif
