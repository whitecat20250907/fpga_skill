Display-only RGA 1.10.1 / driver 1.3.7. Model pixels are never processed here.
Build on RK: g++ -O2 -shared -fPIC rga_preview.cpp -lrga -o librga_preview.so
Original PIL preview remains available when RGA is unavailable.
